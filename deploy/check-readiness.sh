#!/usr/bin/env bash
# Is this machine and AWS account ready to deploy ForexMatch?
#
#   ./deploy/check-readiness.sh
#
# Run it when you want to know whether the blockers have cleared. Exits 0 only
# when everything needed for a deploy is in place.
set -uo pipefail

REGION="${AWS_REGION:-us-east-1}"
MODEL="${BEDROCK_MODEL_ID:-global.anthropic.claude-sonnet-4-6}"
BLOCKERS=0

ok()   { printf '  \033[32m✓\033[0m %-28s %s\n' "$1" "${2:-}"; }
bad()  { printf '  \033[31m✗\033[0m %-28s %s\n' "$1" "${2:-}"; BLOCKERS=$((BLOCKERS+1)); }
warn() { printf '  \033[33m!\033[0m %-28s %s\n' "$1" "${2:-}"; }

echo "ForexMatch deployment readiness"
echo

echo "Local tooling"
command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 \
  && ok "docker" "$(docker version --format '{{.Server.Version}}' 2>/dev/null)" \
  || bad "docker" "not running — 'colima start'"
command -v aws >/dev/null 2>&1 && ok "aws cli" "$(aws --version 2>&1 | cut -d' ' -f1)" || bad "aws cli" "not installed"
command -v vercel >/dev/null 2>&1 && ok "vercel cli" "$(vercel --version 2>&1 | tail -1)" || warn "vercel cli" "not installed"

echo
echo "AWS account"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [[ -n "$ACCOUNT" ]]; then
  ok "authenticated" "account $ACCOUNT"
else
  bad "authenticated" "session expired — run 'aws login'"
fi

CREATED=$(aws account get-account-information --region "$REGION" \
  --query AccountCreatedDate --output text 2>/dev/null)
if [[ -n "$CREATED" && "$CREATED" != "None" ]]; then
  AGE=$(python3 -c "
from datetime import datetime, timezone
c = datetime.fromisoformat('$CREATED'.replace('Z','+00:00'))
print(f\"{(datetime.now(timezone.utc)-c).total_seconds()/3600:.0f}\")" 2>/dev/null)
  if [[ -n "$AGE" && "$AGE" -lt 24 ]]; then
    warn "account age" "${AGE}h — new accounts can take 24h+ to fully activate"
  else
    ok "account age" "${AGE}h"
  fi
fi

echo
echo "Services"
if aws bedrock-runtime converse --region "$REGION" --model-id "$MODEL" \
     --messages '[{"role":"user","content":[{"text":"ok"}]}]' \
     --inference-config '{"maxTokens":5}' >/dev/null 2>&1; then
  ok "bedrock" "$MODEL"
else
  REASON=$(aws bedrock-runtime converse --region "$REGION" --model-id "$MODEL" \
    --messages '[{"role":"user","content":[{"text":"ok"}]}]' \
    --inference-config '{"maxTokens":5}' 2>&1 \
    | grep -oE "INVALID_PAYMENT_INSTRUMENT|use case details|AccessDenied|SubscriptionRequired" | head -1)
  bad "bedrock" "${REASON:-unavailable}"
fi

if aws apprunner list-services --region "$REGION" >/dev/null 2>&1; then
  ok "app runner" "available"
else
  bad "app runner" "SubscriptionRequiredException — account not activated for it"
fi

for svc in "ecr describe-repositories" "rds describe-db-instances" "secretsmanager list-secrets"; do
  name=$(echo "$svc" | cut -d' ' -f1)
  aws $svc --region "$REGION" >/dev/null 2>&1 && ok "$name" "available" || bad "$name" "unavailable"
done

echo
if [[ "$BLOCKERS" -eq 0 ]]; then
  echo "Ready to deploy. Next: deploy/README.md"
  exit 0
fi
echo "$BLOCKERS blocker(s). Deploy will fail until these clear."
exit 1
