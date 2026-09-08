# ForexMatch

**An AI agent that researches and recommends the best forex card for an Indian
student, based on where they're going, how they'll spend, and what they care
about.**

> Tell us where you're going, how you'll spend, and what matters to you.
> We'll find the forex card that fits you.

Built for the **Agents for Humans Hackathon** — Everyday Agents track.

---

## The problem

An Indian student going abroad needs a forex card before they leave. Choosing
one is genuinely hard:

- Fees are scattered across issuance, reload, ATM withdrawal, cross-currency
  markup, replacement and inactivity charges — quoted in different currencies,
  on different pages, in different PDFs.
- The cheapest card *on paper* depends entirely on how you actually spend. A
  card with no issuance fee but a £5 ATM charge is a bad deal for someone who
  withdraws cash weekly, and a great one for someone who never does.
- Comparison sites are affiliate-driven and rarely show their working.
- Asking a chatbot gets you a confident answer built from a stale memory of a
  fee page, with no source and no arithmetic.

## The solution

ForexMatch is not "ask an LLM which card is best". It is an agent that
understands your situation, looks up **verified** card data, fetches today's
reference rate, calculates what each card would actually cost *you*, ranks them
with **deterministic code**, and then explains the result and hands you the
provider's own application link.

The division of labour is strict:

| The language model does | The language model never does |
| --- | --- |
| Hold the conversation | Decide any fee |
| Extract your requirements | Decide any FX markup |
| Ask useful follow-up questions | Decide which currencies a card supports |
| Choose which tools to call | Calculate any cost |
| Explain the result | Choose the winning card |

Fees, markups, currencies and scores come from PostgreSQL and pure Python. The
model is handed the ranking as a fact to explain.

---

## Architecture

```
Natural language → Strands agent → structured profile → verified card data
   → reference FX rate → deterministic cost model → deterministic ranking
   → agent explanation → recommendation UI → application link
```

Full diagrams, including the request sequence and the deployment topology:
[`docs/architecture.md`](docs/architecture.md).

```
frontend/   Next.js 16 · TypeScript · Tailwind 4 · App Router
backend/    FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · PostgreSQL
  app/agent/           Strands agent, prompts, ten tools
  app/recommendation/  pure engine: calculator, scorer, engine, service
  app/fx/              reference rates behind a provider protocol
  app/research/        web research, degrades honestly when unavailable
  app/verification/    proposes changes; never auto-writes
  data/cards/          the sourced catalogue, as JSON
agentcore/  Bedrock AgentCore Runtime adapter
docs/       architecture
```

## The agent

Built on the **Strands Agents SDK**, running on **Amazon Bedrock**. The model is
configured entirely through the environment (`BEDROCK_MODEL_ID`), so it is never
hard-coded and can be changed or swapped for another provider.

The core is a plain callable:

```python
async def run_agent(session_id: UUID | None, message: str, db: AsyncSession) -> AgentResponse
```

FastAPI and AgentCore are both thin wrappers over it. Nothing in the business
logic knows which one is calling.

### Tools

Ten narrow tools, no `do_everything()`:

| Tool | Purpose |
| --- | --- |
| `get_user_profile` | What we already know — so the agent doesn't re-ask |
| `update_user_profile` | Record what was learned, including ranges and priorities |
| `search_cards` | Find candidates in the verified catalogue |
| `get_card_details` | Every published fee, limit, benefit and source for one card |
| `research_card` | Check the provider's current information on the web |
| `get_fx_rate` | Today's mid-market reference rate |
| `calculate_card_cost` | Deterministic cost for one card |
| `compare_cards` | Run the ranking engine — the only route to a recommendation |
| `get_application_link` | The provider's official application route |
| `get_card_sources` | Documents and verification dates behind a card's data |

Every call is timed and written to `tool_events`, and streamed to the browser as
it happens. The activity feed is a view of that table, so the work it shows is
work that actually occurred.

## Recommendation engine

```python
recommend(profile, cards, fx) -> RecommendationResult   # pure, deterministic
```

No I/O, no model, no state. Same inputs, same output — which is what makes the
ranking rules testable and the result explainable.

**Cost model.** Issuance + reloads + ATM withdrawals + cross-currency charges,
priced against an expected usage profile derived from the user's answers. Every
substituted value is recorded as an assumption and shown in the UI.

**Scoring.** Six components — cost, ATM, currency support, convenience, rewards,
security — each 0–100 with the sentence that explains it, combined using the
user's weights (normalised to sum to 1). Scores are rounded to whole numbers:
`93.7284%` is false precision.

**Confidence** is graded on data completeness, freshness, source count and the
margin between the top two. Cards within two points are reported as tied rather
than separated by a decimal point.

**Hard filters** remove only genuinely unusable cards — discontinued products,
no application route, a currency the card cannot serve. Being merely worse is
what scoring is for.

## Data trust

Every fee, limit, benefit, currency and eligibility row carries a **NOT NULL**
`source_id`. It is structurally impossible to store an unsourced financial fact.

The catalogue distinguishes three states that must never be conflated:

- **`is_waived`** — the provider states the charge is nil. Shown as free.
- **`is_unknown`** — the provider publishes no figure. **Not zero.**
- **`NULL`** — not verified.

Where a charge is unknown, costing substitutes the **highest** figure among the
compared cards, flags the line and explains it. A card can never rank better
because its issuer published less.

### What's in the catalogue

14 real products from 6 Indian providers — Axis Bank, HDFC Bank, ICICI Bank,
YES BANK, BookMyForex and Thomas Cook — with 265 sourced facts.

Provenance is uneven and the data records that honestly:

- **Axis** publishes a complete PDF fee table, so both Axis cards are fully
  priced across all 16 currencies, including per-currency ATM and replacement
  charges.
- **HDFC's** retail pages sit behind bot protection that refused automated
  retrieval. Their figures are stored against the official fee-schedule URLs and
  flagged for re-verification.
- Where a provider says only "minimal ATM fees", the fee is `is_unknown`.
- Currency lists that could not be verified are left empty, and the engine says
  *"we cannot confirm it holds GBP"* rather than asserting that it does not.

This is below the 15–30 target in the build specification. Adding a fifteenth
card would have meant inventing data, which the specification forbids and the
seed loader rejects.

## Running locally

**Prerequisites:** Python 3.11+, Node 20+, PostgreSQL 14+. AWS credentials with
Bedrock access are optional — see the offline mode below.

```bash
git clone https://github.com/shlokpanjabi/forexmatch.git
cd forexmatch
```

### 1. Database

```bash
docker compose up -d postgres
```

Or use a local PostgreSQL and `createdb forexmatch`.

### 2. Backend

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e "./backend[dev]"

cp .env.example backend/.env      # then edit
cd backend
alembic upgrade head
python scripts/seed_cards.py
uvicorn app.main:app --reload
```

The API is on http://localhost:8000, with docs at `/docs`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000.

### Running without AWS

```bash
MODEL_PROVIDER=mock uvicorn app.main:app --reload
```

This selects an offline demo model that drives the **real** tools — the real
catalogue, a real FX call and the real ranking engine — using keyword matching
instead of language understanding. Every tool event and the recommendation are
genuine; only the conversation is crude. It labels itself as such in every reply.

## Environment variables

Secrets are backend-only and never reach the browser. **AWS credentials are
deliberately not read from `.env`** — Bedrock uses the standard boto3 credential
chain (`aws configure`, `aws sso login`, or an execution role), so only
non-secret AWS settings are configured here.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://localhost:5432/forexmatch` | PostgreSQL, asyncpg driver |
| `ENVIRONMENT` | `development` | `development` / `test` / `staging` / `production` |
| `LOG_LEVEL` | `INFO` | Structured log level |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `MODEL_PROVIDER` | `bedrock` | `bedrock`, or `mock` for offline |
| `AWS_REGION` | `us-east-1` | Bedrock region |
| `BEDROCK_MODEL_ID` | `global.anthropic.claude-sonnet-4-6` | Model to run the agent on |
| `BEDROCK_STREAMING` | `true` | `false` if the account is cleared for Converse but not ConverseStream |
| `FX_PROVIDER` | `frankfurter` | `frankfurter`, `exchangerate_host`, `static` |
| `FX_API_KEY` | — | Only for `exchangerate_host` |
| `FX_CACHE_TTL_SECONDS` | `3600` | Reference-rate cache lifetime |
| `RESEARCH_PROVIDER` | `bedrock` | `bedrock` or `none` |
| `ADMIN_SECRET` | — | Required for `/admin/*`; unset locks the routes |
| `POSTHOG_API_KEY` | — | Optional; absent disables analytics entirely |
| `SENTRY_DSN` | — | Optional error monitoring |

Frontend: `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).

## Testing

```bash
cd backend && pytest              # 153 tests
cd frontend && npm test           # 15 tests
```

Backend tests run against a real PostgreSQL database (`forexmatch_test`, created
automatically) because NULL handling, CHECK constraints and JSONB behaviour are
part of what is being tested.

Coverage includes the cost arithmetic, the ranking rules, catalogue quality
gates that run against the seed files themselves, the agent loop driven by a
scripted model, the HTTP contracts, and the honesty rules — that an unpublished
fee can never make a card rank cheaper, and that a zero fee must be an explicit
published claim rather than an incidental zero.

## Deployment

**Backend** — `backend/Dockerfile` builds a non-root image suitable for ECS,
App Runner or any container host. Run `alembic upgrade head` as a separate
deployment step so scaling cannot race on the schema.

**Frontend** — `npm run build` produces a standard Next.js build.

**Database** — Amazon RDS for PostgreSQL.

**Agent** — optionally Amazon Bedrock AgentCore Runtime. See
[`agentcore/README.md`](agentcore/README.md). The backend remains a conventional
FastAPI application either way.

### Bedrock account setup

Two operations are gated separately in Bedrock, and an account can be cleared for
one and not the other:

- If model calls fail with *"Model use case details have not been submitted"*,
  complete the Anthropic use-case form in the Bedrock console.
- If only streaming fails, set `BEDROCK_STREAMING=false` to use the
  non-streaming Converse API.
- Built-in web search requires the same form. Without it, `research_card`
  returns `unavailable` with the reason attached, and the agent is instructed to
  rely on stored data and say it could not re-check — never to fill the gap from
  memory.

## Safety and privacy

- Every recommendation carries: *"This is an informational comparison, not
  financial advice. Card fees and terms can change. Check the provider's current
  terms before applying."*
- The app never collects passport numbers, bank accounts, card numbers, Aadhaar,
  PAN or KYC documents, and the agent is instructed not to ask.
- Analytics events and properties are both allow-listed server-side.
- Affiliate URLs are supported but resolved only *after* a winner is chosen —
  ranking cannot see them.

## Licence

MIT — see [LICENSE](LICENSE).
