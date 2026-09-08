# AgentCore deployment

The agent is a plain Python callable, so deploying it to Amazon Bedrock
AgentCore Runtime needs no changes to the application. `entrypoint.py` is the
only adapter, and it does nothing but unpack a payload and call
`run_agent(session_id, message, db)`.

Local development does not depend on any of this — run the FastAPI backend
instead (see the root README).

## Prerequisites

- AWS credentials with Bedrock access, resolved through the standard chain
  (`aws configure`, `aws sso login`, or an execution role). Nothing here reads
  access keys from a file.
- A PostgreSQL instance reachable from the runtime, with `DATABASE_URL` set.
- The AgentCore CLI: `pip install bedrock-agentcore-starter-toolkit`

## Commands

```bash
# Run the entrypoint locally against the same code path AgentCore will use
agentcore dev

# Configure and deploy
agentcore configure --entrypoint agentcore/entrypoint.py
agentcore launch

# Send a turn
agentcore invoke '{"message": "I am going to the UK for a two year master'\''s."}'
```

## Payload

```json
{ "message": "…", "session_id": "<uuid, optional>" }
```

Omitting `session_id` starts a new conversation; the response carries the id to
send with the next turn. The response shape matches `POST /api/chat`, so a
client can move between the HTTP API and AgentCore unchanged.

## Configuration

The runtime needs the same environment as the backend, minus anything secret:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL, using the `postgresql+asyncpg://` driver |
| `AWS_REGION` | Bedrock region |
| `BEDROCK_MODEL_ID` | Model to run the agent on |
| `BEDROCK_STREAMING` | `false` if the account is cleared for Converse but not ConverseStream |

AWS credentials are deliberately absent from that list — the execution role
supplies them.
