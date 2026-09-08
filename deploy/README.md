# Deploying ForexMatch

Frontend on **Vercel**, backend on **AWS App Runner**, database on **Amazon RDS
for PostgreSQL**, model on **Amazon Bedrock**.

Every command below is one you run. Nothing here is applied automatically,
because most of these steps create billable resources.

---

## 0. Before you start

| Requirement | Check |
| --- | --- |
| A valid payment method on the AWS account | Bedrock bills through AWS Marketplace and refuses to serve without one |
| Docker running locally | `docker info` |
| AWS CLI authenticated | `aws sts get-caller-identity` |
| Anthropic use-case form submitted | `aws bedrock get-use-case-for-model-access --region us-east-1` |

### Deploying before Bedrock works

Bedrock inference and the rest of the stack are gated separately. Bedrock bills
through **AWS Marketplace**, which needs a card on file; RDS, App Runner and ECR
bill through ordinary AWS billing, which accepts Direct Debit. So if you are
waiting on a payment method to authorise, you can still deploy everything and
have a working public demo today.

Set `MODEL_PROVIDER=mock` in the App Runner environment (step 7). That selects
the offline model, which drives the **real** tools — the real catalogue, a real
FX call and the real ranking engine — using keyword matching instead of a
language model. Tool activity and recommendations are genuine; only the
conversation is crude, and every reply says so.

When the card clears, flip it with no rebuild and no other change:

```bash
aws apprunner update-service --service-arn $SERVICE_ARN \
  --source-configuration '{"ImageRepository":{"ImageConfiguration":{"RuntimeEnvironmentVariables":{"MODEL_PROVIDER":"bedrock"}}}}'
```

That one-line switch is the reason the model layer is environment-driven.

Confirm Bedrock actually answers before deploying anything — it is the cheapest
failure to find early:

```bash
aws bedrock-runtime converse --region us-east-1 \
  --model-id global.anthropic.claude-sonnet-4-6 \
  --messages '[{"role":"user","content":[{"text":"say OK"}]}]' \
  --inference-config '{"maxTokens":8}'
```

Set these once per shell:

```bash
export AWS_REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

> **Cost.** RDS `db.t4g.micro` and 20 GB of storage are free-tier eligible for
> 12 months on a new account; after that roughly $12–15/month. App Runner at
> 1 vCPU / 2 GB is roughly $5–25/month depending on traffic — it does **not**
> scale to zero. Bedrock is billed per token. Delete the resources when the
> hackathon is over (see the teardown section).

---

## 1. Database

Find the default VPC and its subnets:

```bash
export VPC_ID=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' --output text)
export SUBNET_IDS=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC_ID \
  --query 'Subnets[].SubnetId' --output text | tr '\t' ',')
echo "VPC=$VPC_ID SUBNETS=$SUBNET_IDS"
```

Create a security group for the database:

```bash
export DB_SG=$(aws ec2 create-security-group \
  --group-name forexmatch-db --description "ForexMatch RDS" \
  --vpc-id $VPC_ID --query GroupId --output text)
```

Allow your own machine in, so you can run migrations:

```bash
export MY_IP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress --group-id $DB_SG \
  --protocol tcp --port 5432 --cidr ${MY_IP}/32
```

Choose a database password and keep it out of your shell history — this reads it
without echoing:

```bash
read -rs -p "New database password: " DB_PASSWORD && export DB_PASSWORD && echo
```

Create the instance:

```bash
aws rds create-db-instance \
  --db-instance-identifier forexmatch \
  --db-instance-class db.t4g.micro \
  --engine postgres --engine-version 17.11 \
  --allocated-storage 20 --storage-type gp3 --storage-encrypted \
  --master-username forexmatch --master-user-password "$DB_PASSWORD" \
  --db-name forexmatch \
  --vpc-security-group-ids $DB_SG \
  --publicly-accessible \
  --backup-retention-period 7 \
  --no-multi-az

aws rds wait db-instance-available --db-instance-identifier forexmatch

export DB_HOST=$(aws rds describe-db-instances --db-instance-identifier forexmatch \
  --query 'DBInstances[0].Endpoint.Address' --output text)
echo "DB_HOST=$DB_HOST"
```

> `--publicly-accessible` is what lets you run migrations from your laptop. The
> security group is what actually restricts access, and it currently allows only
> your IP. If you would rather not expose it at all, drop that flag and run
> migrations from a bastion host inside the VPC instead.

---

## 2. Secrets

The database URL contains a password, so it goes in Secrets Manager rather than
an environment variable on the service:

```bash
aws secretsmanager create-secret --name forexmatch/database-url \
  --secret-string "postgresql+asyncpg://forexmatch:${DB_PASSWORD}@${DB_HOST}:5432/forexmatch"

aws secretsmanager create-secret --name forexmatch/admin-secret \
  --secret-string "$(openssl rand -hex 32)"
```

---

## 3. Migrate and seed

From the repository root, with the backend virtualenv active:

```bash
DATABASE_URL="postgresql+asyncpg://forexmatch:${DB_PASSWORD}@${DB_HOST}:5432/forexmatch" \
  ./deploy/migrate.sh
```

That applies the migrations and loads the 14-card catalogue. Re-running it is
safe — cards are matched by slug and their facts rebuilt.

---

## 4. IAM roles

Two roles: one App Runner assumes to pull the image, one the running container
assumes to reach Bedrock and Secrets Manager.

```bash
# Role App Runner uses to pull from ECR
aws iam create-role --role-name ForexMatchAppRunnerECRAccessRole \
  --assume-role-policy-document file://deploy/iam/apprunner-ecr-trust.json
aws iam attach-role-policy --role-name ForexMatchAppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

# Role the container runs as
aws iam create-role --role-name ForexMatchAppRunnerInstanceRole \
  --assume-role-policy-document file://deploy/iam/apprunner-instance-trust.json
aws iam put-role-policy --role-name ForexMatchAppRunnerInstanceRole \
  --policy-name ForexMatchRuntime \
  --policy-document file://deploy/iam/instance-policy.json
```

The instance policy grants only `bedrock:InvokeModel`,
`bedrock:InvokeModelWithResponseStream` on Anthropic models, and
`secretsmanager:GetSecretValue` on `forexmatch/*`. Nothing else.

---

## 5. VPC connector

App Runner needs a route into the VPC to reach RDS:

```bash
export CONNECTOR_SG=$(aws ec2 create-security-group \
  --group-name forexmatch-apprunner --description "ForexMatch App Runner egress" \
  --vpc-id $VPC_ID --query GroupId --output text)

# Let the service reach the database
aws ec2 authorize-security-group-ingress --group-id $DB_SG \
  --protocol tcp --port 5432 --source-group $CONNECTOR_SG

export CONNECTOR_ARN=$(aws apprunner create-vpc-connector \
  --vpc-connector-name forexmatch \
  --subnets ${SUBNET_IDS//,/ } \
  --security-groups $CONNECTOR_SG \
  --query 'VpcConnector.VpcConnectorArn' --output text)
echo "CONNECTOR_ARN=$CONNECTOR_ARN"
```

---

## 6. Build and push the image

```bash
./deploy/push-image.sh
```

The script creates the ECR repository if needed and builds for `linux/amd64` —
App Runner runs x86_64, and an arm64 image built on an Apple Silicon Mac will
start and immediately die with an exec format error.

---

## 7. Create the App Runner service

Fill in the placeholders, then create the service:

```bash
sed -e "s/REPLACE_ACCOUNT_ID/${ACCOUNT_ID}/g" \
    -e "s|REPLACE_VPC_CONNECTOR_ARN|${CONNECTOR_ARN}|g" \
    -e "s|https://REPLACE_YOUR_APP.vercel.app|http://localhost:3000|g" \
    deploy/apprunner-service.json > /tmp/apprunner.json

aws apprunner create-service --cli-input-json file:///tmp/apprunner.json

aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='forexmatch-api']"
```

`CORS_ORIGINS` is set to localhost for now; step 9 replaces it with the real
Vercel domain, which you will not know until the frontend is deployed.

Once it reports `RUNNING`:

```bash
export API_URL="https://$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='forexmatch-api'].ServiceUrl" --output text)"
curl -s $API_URL/health
curl -s "$API_URL/api/cards?currency=GBP" | head -c 400
```

---

## 8. Frontend on Vercel

```bash
npm install -g vercel
cd frontend
vercel login
vercel link          # create a new project when prompted
```

Point it at the API and deploy:

```bash
vercel env add NEXT_PUBLIC_API_BASE_URL production   # paste the App Runner URL
vercel --prod
```

Vercel builds from `frontend/` as the project root. If you connect the GitHub
repository through the dashboard instead, set **Root Directory** to `frontend`.

---

## 9. Close the CORS loop

The browser calls the API directly, so the API has to name the Vercel domain:

```bash
export SERVICE_ARN=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='forexmatch-api'].ServiceArn" --output text)

aws apprunner update-service --service-arn $SERVICE_ARN \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "'"${ACCOUNT_ID}"'.dkr.ecr.'"${AWS_REGION}"'.amazonaws.com/forexmatch-api:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "ENVIRONMENT": "production",
          "AWS_REGION": "'"${AWS_REGION}"'",
          "MODEL_PROVIDER": "bedrock",
          "BEDROCK_MODEL_ID": "global.anthropic.claude-sonnet-4-6",
          "FX_PROVIDER": "frankfurter",
          "RESEARCH_PROVIDER": "bedrock",
          "CORS_ORIGINS": "https://YOUR-APP.vercel.app"
        },
        "RuntimeEnvironmentSecrets": {
          "DATABASE_URL": "arn:aws:secretsmanager:'"${AWS_REGION}"':'"${ACCOUNT_ID}"':secret:forexmatch/database-url",
          "ADMIN_SECRET": "arn:aws:secretsmanager:'"${AWS_REGION}"':'"${ACCOUNT_ID}"':secret:forexmatch/admin-secret"
        }
      }
    }
  }'
```

Vercel preview deployments get their own domains. If you want those to work too,
add them to `CORS_ORIGINS` as a comma-separated list.

---

## 10. Check it end to end

Open the Vercel URL and send the demo message. You should see the agent's real
tool sequence, then a recommendation with sources and an apply button.

From the command line:

```bash
curl -s -X POST $API_URL/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"I am an Indian student going to the UK for two years, about £1,100 a month, not much cash."}' \
  | python3 -m json.tool | head -40
```

---

## Redeploying

```bash
./deploy/push-image.sh                     # AutoDeployments picks it up
DATABASE_URL=... ./deploy/migrate.sh       # only when migrations changed
cd frontend && vercel --prod
```

---

## Teardown

App Runner does not scale to zero, so it bills while it exists. Remove
everything when you are done:

```bash
aws apprunner delete-service --service-arn $SERVICE_ARN
aws apprunner delete-vpc-connector --vpc-connector-arn $CONNECTOR_ARN
aws rds delete-db-instance --db-instance-identifier forexmatch \
  --skip-final-snapshot --delete-automated-backups
aws secretsmanager delete-secret --secret-id forexmatch/database-url --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id forexmatch/admin-secret --force-delete-without-recovery
aws ecr delete-repository --repository-name forexmatch-api --force
aws iam delete-role-policy --role-name ForexMatchAppRunnerInstanceRole --policy-name ForexMatchRuntime
aws iam delete-role --role-name ForexMatchAppRunnerInstanceRole
aws iam detach-role-policy --role-name ForexMatchAppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
aws iam delete-role --role-name ForexMatchAppRunnerECRAccessRole
```

---

## Troubleshooting

**`INVALID_PAYMENT_INSTRUMENT`** — Bedrock bills through AWS Marketplace, which
needs a **card**. A Bacs Direct Debit mandate shown as *Authorization Pending*
does not satisfy it, and generally will not once active either. Add a credit or
debit card in the Billing console, wait two minutes, retry. Meanwhile deploy
with `MODEL_PROVIDER=mock` — see "Deploying before Bedrock works" above.

**`Model use case details have not been submitted`** — open any Anthropic model
in the Bedrock playground and complete the form. Once per account.

**Streaming fails but ordinary calls work** — Converse and ConverseStream are
cleared separately. Set `BEDROCK_STREAMING=false`.

**Service stuck in `OPERATION_IN_PROGRESS`, then rolls back** — check the
application logs; almost always the database is unreachable, meaning the
connector security group is not allowed into `forexmatch-db` on 5432.

```bash
aws logs tail /aws/apprunner/forexmatch-api --follow
```

**`exec format error`** — the image was built for arm64. Rebuild with
`./deploy/push-image.sh`, which forces `linux/amd64`.

**CORS errors in the browser** — `CORS_ORIGINS` must contain the exact Vercel
origin including the scheme and no trailing slash.
