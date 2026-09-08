# ForexMatch — End-to-End Build Specification

## 0. IMPORTANT: READ THIS FIRST

You are Claude Code acting as the primary engineering agent for this project.

Build the product described in this document end to end.

Do NOT redesign the product concept.
Do NOT substitute the architecture with another framework.
Do NOT replace Strands Agents with LangChain, LangGraph, OpenAI Agents SDK, or another agent framework.
Do NOT make the recommendation engine an LLM-only decision.
Do NOT spend significant time polishing visual design.

The product owner will handle detailed visual design later.

Your job is to build a complete, functional, production-quality MVP with:

- frontend
- backend
- PostgreSQL database
- Strands AI agent
- web research
- forex-rate retrieval
- deterministic recommendation engine
- cost calculations
- card data verification
- application links
- analytics hooks
- tests
- seed data
- documentation
- deployment configuration

The system must work end to end locally before deployment.

---

# 1. PRODUCT

## Working name

ForexMatch

The name can be changed later.

## One-line description

An AI agent that researches and recommends the best forex card for an Indian student based on their destination, spending habits and personal priorities.

## Core user promise

> Tell us where you're going, how you'll spend, and what matters to you. We'll find the forex card that fits you.

## Target user

Primarily:

- Indian students going abroad for university
- students who need a forex card before departure
- students already abroad who are still choosing/replacing a forex card

Secondary future audiences:

- tourists
- business travellers
- frequent international travellers

Do not expand the product beyond forex cards in this version.

---

# 2. PRODUCT PRINCIPLE

The product is NOT:

> "Ask an LLM which forex card is best."

The product IS:

> "An agent that understands your situation, researches current forex-card information, calculates the actual expected cost for your usage, compares products, explains the reasoning and sends you to the appropriate application flow."

The LLM is responsible for:

- conversation
- extracting user requirements
- asking useful follow-up questions
- deciding which tools to call
- researching information
- explaining results
- handling ambiguity

The LLM is NOT the source of truth for:

- fees
- FX markup
- ATM charges
- supported currencies
- eligibility
- calculated costs
- recommendation scores

Those must come from structured data and deterministic code.

---

# 3. HACKATHON CONTEXT

This project is being built for the Agents for Humans Hackathon.

The project must use the Strands Agents SDK.

The strongest track is:

## Everyday Agents

The project addresses money / financial decision-making for students.

The agent must demonstrate real work rather than merely answering a question.

The demo should visibly show the agent:

1. understanding the student's situation
2. extracting requirements
3. researching cards
4. checking current data
5. retrieving an FX rate
6. calculating expected costs
7. comparing cards
8. producing a recommendation
9. providing an application path

The agent must be genuinely involved in this process.

Do not fake agent activity in the UI.

---

# 4. LOCKED TECHNOLOGY STACK

## Frontend

- Next.js
- TypeScript
- App Router
- Tailwind CSS
- shadcn/ui where useful
- React
- TanStack Query if useful for server state

Do not over-engineer the frontend.

## Backend

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic

## Agent

- Strands Agents SDK
- Python

Primary model:

- Amazon Bedrock
- Claude Sonnet 4.6

Model configuration must be environment-driven so the model can be changed later.

## Database

PostgreSQL.

Use UUID primary keys.

Use SQLAlchemy models and Alembic migrations.

## Deployment

Target:

- AWS
- Amazon Bedrock
- Amazon Bedrock AgentCore Runtime for the agent if practical

The backend should remain deployable as a conventional FastAPI application even if AgentCore deployment is configured separately.

## Analytics

PostHog.

Analytics must be abstracted so the app still works if PostHog credentials are missing.

## Error monitoring

Sentry integration should be optional and environment-driven.

## Testing

- pytest
- pytest-asyncio
- HTTPX for API tests
- frontend tests where useful

---

# 5. HIGH-LEVEL ARCHITECTURE

```text
                         ┌─────────────────────┐
                         │      Next.js        │
                         │      Frontend       │
                         └──────────┬──────────┘
                                    │
                                    │ HTTPS
                                    ▼
                         ┌─────────────────────┐
                         │       FastAPI       │
                         │       Backend       │
                         └──────────┬──────────┘
                                    │
                  ┌─────────────────┼──────────────────┐
                  │                 │                  │
                  ▼                 ▼                  ▼
        ┌─────────────────┐ ┌───────────────┐ ┌─────────────────┐
        │ Strands Agent   │ │ Recommendation│ │ PostgreSQL      │
        │                 │ │ Engine        │ │                 │
        │ Conversation    │ │               │ │ Card data       │
        │ Tool calling    │ │ Cost calc     │ │ Sources         │
        │ Research        │ │ Ranking       │ │ Verification    │
        └───────┬─────────┘ └───────┬───────┘ │ History         │
                │                   │         └─────────────────┘
       ┌────────┼────────┐          │
       │        │        │          │
       ▼        ▼        ▼          ▼
   Web Search  FX API  Card DB  Calculators
       │
       ▼
 Official provider websites
```

---

# 6. CORE ARCHITECTURAL RULE

Use this pipeline:

```text
Natural language
       ↓
Strands Agent
       ↓
Structured User Profile
       ↓
Research / Retrieval
       ↓
Verified Card Data
       ↓
Deterministic Cost Calculation
       ↓
Deterministic Recommendation Ranking
       ↓
Strands Agent Explanation
       ↓
Recommendation UI
       ↓
Application CTA
```

Never:

```text
User message → LLM → "I think HDFC is best"
```

---

# 7. USER JOURNEY

## Step 1 — User starts conversation

Example:

> I'm going to the UK for my master's for 2 years. I'll probably spend around £1,000–£1,200 a month and won't use cash very much.

The agent should extract:

```json
{
  "destination_country": "United Kingdom",
  "destination_currency": "GBP",
  "duration_months": 24,
  "monthly_spend": {
    "min": 1000,
    "max": 1200,
    "currency": "GBP"
  },
  "atm_usage": "low"
}
```

Do not require the user to fill a long form.

---

# 8. REQUIRED USER PROFILE

Create a Pydantic model:

```python
UserProfile
```

Fields:

```text
destination_country
destination_currencies
trip_type
trip_duration_months
monthly_spend_min
monthly_spend_max
monthly_spend_currency
atm_usage
atm_withdrawals_per_month
average_atm_withdrawal
primary_spending_categories
expected_reload_frequency
needs_multiple_currencies
priority_cost
priority_atm
priority_rewards
priority_convenience
priority_currency_support
priority_security
currently_abroad
departure_date
student_status
```

Not every field is required.

---

# 9. USER UNCERTAINTY

Students often don't know exact spending.

This is important.

The user must be able to say:

- "not sure"
- "probably around £1,000"
- "maybe £1,500"
- "I don't know how much cash I'll need"

Do NOT force false precision.

Represent uncertain values as ranges.

Example:

```json
{
  "monthly_spend_min": 900,
  "monthly_spend_max": 1300,
  "confidence": "estimated"
}
```

The UI should later communicate:

> Estimated monthly spend: £900–£1,300

The user must be able to change this after the recommendation.

---

# 10. FOLLOW-UP QUESTIONS

The agent should only ask questions that materially affect the recommendation.

High-value questions:

1. Where are you going?
2. How long are you staying?
3. Roughly how much will you spend per month?
4. How often will you withdraw cash?
5. Will you mainly spend in one currency or multiple currencies?
6. What matters most: lowest cost, convenience, rewards, ATM access, etc.?

Do NOT ask all questions mechanically.

The agent should infer what it can.

Example:

User:

> I'm moving to Manchester for a two-year master's and probably spend £1,100 a month.

Do not ask:

> What country are you travelling to?

The agent knows the UK.

---

# 11. PRIORITY SYSTEM

The user can define what matters.

The recommendation engine must support weighted preferences.

Default weights:

```text
cost: 0.40
atm: 0.15
currency_support: 0.15
convenience: 0.15
rewards: 0.10
security: 0.05
```

But these are defaults only.

Users can override them.

Example:

> I don't care about rewards, I just want the cheapest card.

Then:

```text
cost: 0.70
atm: 0.10
currency_support: 0.05
convenience: 0.10
rewards: 0.00
security: 0.05
```

Normalize all weights to sum to 1.

---

# 12. CARD DATABASE

PostgreSQL is the source of truth.

Create:

## cards

Fields:

```text
id UUID
provider
card_name
slug
card_type
network
description
is_active
application_url
affiliate_url
created_at
updated_at
```

## card_currencies

```text
id
card_id
currency_code
supported
direct_wallet
```

## card_fees

```text
id
card_id
fee_type
amount
currency
percentage
min_amount
max_amount
conditions
effective_from
effective_to
source_id
```

Possible fee types:

```text
issuance
reload
atm_withdrawal
cross_currency
replacement
encashment
inactivity
balance_enquiry
transaction
other
```

## card_limits

```text
id
card_id
limit_type
amount
currency
period
conditions
source_id
```

Examples:

```text
daily_atm
daily_spend
monthly_reload
annual_reload
wallet_limit
```

## card_benefits

```text
id
card_id
benefit_type
description
value
conditions
source_id
```

## card_eligibility

```text
id
card_id
criterion
value
description
source_id
```

## sources

```text
id
card_id
url
domain
title
source_type
retrieved_at
last_verified_at
content_hash
notes
```

source_type:

```text
official_product_page
official_fee_schedule
official_terms
official_faq
secondary_source
```

Official sources should always be preferred.

---

# 13. SOURCE TRUST HIERARCHY

When verifying a financial-product fact:

### Priority 1

Official provider product page.

### Priority 2

Official provider fee schedule.

### Priority 3

Official terms and conditions.

### Priority 4

Official FAQ / support documentation.

### Priority 5

Reliable secondary source.

Never prefer a blog over an official fee schedule.

Every financial fact must have:

- source URL
- source type
- last verified date

---

# 14. INITIAL CARD DATASET

Seed approximately 15–30 real Indian forex products.

Start with products from:

- HDFC Bank
- Axis Bank
- ICICI Bank
- YES BANK
- BookMyForex
- Thomas Cook
- Orient Exchange
- other legitimate Indian forex providers where reliable official data can be verified

Do not invent cards or fees.

The database seed process should only insert data that has a source URL.

If a field cannot be verified:

```text
NULL
```

not:

```text
0
```

Never interpret unknown as free.

---

# 15. KNOWN EXAMPLES FOR INITIAL RESEARCH

The following providers have publicly available product information that can be used as initial research targets:

### HDFC

Products include:

- Regalia ForexPlus
- Multicurrency ForexPlus
- ISIC Student ForexPlus

HDFC currently publishes distinct issuance/reload/ATM structures for these products.

### Axis

Axis has a Multi-Currency Forex Card supporting a published basket of currencies and overseas ATM usage.

### ICICI

ICICI offers Multicurrency Forex Prepaid Cards and describes online card management and overseas usage.

### YES BANK

YES BANK offers Multi-Currency Travel Card products.

### BookMyForex

BookMyForex offers a Multi-Currency Forex Card.

### Thomas Cook

Thomas Cook offers Borderless Travel Card and One Currency Card products.

### Orient Exchange

Orient offers forex-card products including zero-markup positioning.

These are seed candidates only.

Claude Code must verify current data before inserting it.

---

# 16. APPLICATION LINKS

Every card should have:

```text
application_url
```

If an official application page exists, use it.

If the provider only offers an application through a branch or enquiry flow, store that official route.

Do not invent affiliate URLs.

Affiliate support:

```text
affiliate_url nullable
affiliate_provider nullable
affiliate_tracking_enabled boolean
```

Application ranking must NEVER be influenced by affiliate revenue.

If an affiliate relationship is later introduced, display an appropriate disclosure.

---

# 17. RECOMMENDATION ENGINE

Create a dedicated module:

```text
backend/app/recommendation/
```

Files:

```text
calculator.py
scorer.py
models.py
service.py
```

This engine must be deterministic.

The LLM cannot directly choose the winning card.

---

# 18. COST MODEL

Calculate estimated total cost for the user's expected usage.

At minimum:

```text
issuance fees
+ expected reload fees
+ expected ATM fees
+ cross-currency costs
+ replacement/inactivity costs where applicable
```

Do NOT include irrelevant fees.

Example:

User:

```text
24 months
£1,100/month
low ATM usage
1 reload/month
UK only
```

The system should calculate an estimated usage profile.

Example:

```text
annual spend = 13200 GBP
24-month spend = 26400 GBP
reloads = 24
ATM withdrawals = estimated from user profile
```

Then calculate expected card costs.

---

# 19. FX COST MODEL

There are three different concepts:

1. reference/mid-market FX rate
2. provider/card rate
3. provider FX markup/spread

Never pretend they are the same.

The system should explicitly represent:

```text
reference_rate
provider_rate
markup_percentage
```

If only a reference rate is available:

Do not invent provider rate.

Instead:

```text
estimated_reference_conversion
```

and clearly label it.

---

# 20. FX RATE SERVICE

Create:

```text
backend/app/fx/
```

with:

```text
provider.py
service.py
models.py
```

Use an interface:

```python
class FXProvider(Protocol):
    async def get_rate(
        self,
        base_currency: str,
        quote_currency: str
    ) -> FXRate:
        ...
```

The application should not depend directly on one provider.

Recommended v1:

- use a free/reference-rate provider where suitable
- cache rates
- store timestamp
- expose provider name

Do not use a live rate to overwrite historical card data.

---

# 21. FX CACHING

Cache reference rates.

Suggested cache:

```text
currency pair
timestamp
rate
provider
```

Use Redis only if genuinely necessary.

For MVP, PostgreSQL caching is acceptable.

Do not add unnecessary infrastructure.

---

# 22. RECOMMENDATION SCORING

Each card receives component scores from 0–100.

Components:

```text
cost_score
atm_score
currency_score
convenience_score
rewards_score
security_score
```

Final score:

```python
final_score = sum(
    component_score * user_weight
)
```

Never expose meaningless precision such as:

> 93.7284%

Round to:

> 94%

But only display a score if it can be explained.

---

# 23. COST SCORE

Lowest expected cost gets highest score.

Example normalization:

```python
score = 100 * (
    max_cost - card_cost
) / (
    max_cost - min_cost
)
```

Handle equal costs safely.

If all costs are equal:

```text
cost_score = 100
```

Do not divide by zero.

---

# 24. ATM SCORE

Consider:

- ATM fee
- ATM network
- number of expected withdrawals
- withdrawal limits
- international availability

Low ATM user:

ATM score should matter less.

High ATM user:

ATM score becomes important.

---

# 25. CURRENCY SCORE

Consider:

- destination currency directly supported
- direct wallet
- cross-currency fees
- number of supported currencies

Directly supported destination currency should be strongly preferred over forced cross-currency conversion.

---

# 26. CONVENIENCE SCORE

Consider:

- online application
- reload convenience
- online management
- replacement process
- student suitability
- availability

Do not invent convenience scores.

Create explainable feature rules.

---

# 27. REWARDS SCORE

Rewards are secondary.

Consider:

- cashback
- discounts
- airport lounge
- travel benefits
- insurance

Do not allow rewards to overwhelm cost for a student unless the user specifically prioritizes them.

---

# 28. SECURITY SCORE

Consider documented features such as:

- emergency replacement
- fraud protection
- card controls
- transaction alerts
- emergency assistance

Again, score from actual structured data.

---

# 29. HARD FILTERS

Before scoring, remove cards that are clearly unsuitable.

Examples:

- card does not support destination currency and cannot reasonably be used for that destination
- user is ineligible
- product is discontinued
- product is inactive
- application unavailable
- required condition impossible for the user

Do not hard-filter a card merely because it is less optimal.

---

# 30. RESULT STRUCTURE

Return:

```json
{
  "recommended_card": {},
  "alternatives": [],
  "comparison": [],
  "user_profile": {},
  "calculation": {},
  "assumptions": [],
  "sources": []
}
```

---

# 31. TOP THREE

Always return:

1. Best match
2. Alternative
3. Alternative

Unless fewer than three cards actually qualify.

Never artificially create three recommendations.

---

# 32. EXPLANATION

The agent should explain:

### Why this card

Example:

> This is your best match because you're spending mostly in GBP, don't expect to withdraw much cash and care most about keeping costs low.

### Estimated cost

Example:

> Based on £1,100/month and one reload per month, your estimated card-specific fees are approximately £X over 12 months.

### What could change the recommendation

Example:

> If you start withdrawing cash 4–5 times a month, Card B becomes more attractive.

### Why alternatives

Example:

> Card B is slightly more expensive for your current usage but has better ATM economics.

This explanation must be generated from structured recommendation output.

---

# 33. TRANSPARENCY

Every result must allow the user to see:

- card fees used
- assumptions
- FX rate timestamp
- data verification timestamp
- sources

Never hide the calculation.

---

# 34. USER RE-RANKING

After recommendation, users should be able to say:

> Actually I'll probably withdraw cash twice a week.

The agent should:

1. update profile
2. rerun calculation
3. rerun recommendation
4. explain what changed

No need to restart the conversation.

Same for:

> Actually cost doesn't matter, I want rewards.

---

# 35. STRANDS AGENT

Create:

```text
backend/app/agent/
```

Structure:

```text
agent.py
prompts.py
tools/
    profile.py
    cards.py
    research.py
    fx.py
    calculator.py
    recommendation.py
    application.py
```

---

# 36. STRANDS TOOLS

Implement at minimum:

## `get_user_profile`

Returns current structured profile.

## `update_user_profile`

Updates known fields.

## `search_cards`

Searches PostgreSQL for relevant cards.

## `get_card_details`

Returns complete structured card information.

## `research_card`

Researches current provider information using web search.

## `get_fx_rate`

Gets current reference FX rate.

## `calculate_card_cost`

Runs deterministic cost model.

## `compare_cards`

Runs deterministic recommendation engine.

## `get_application_link`

Returns official application URL / affiliate URL if configured.

## `get_card_sources`

Returns supporting sources and verification dates.

---

# 37. TOOL DESIGN

Tools should be narrow.

Do not create one enormous tool:

```text
do_everything()
```

Instead use small tools with clear descriptions.

Each tool must:

- validate input
- return structured output
- handle errors
- log useful metadata
- never expose secrets

---

# 38. AGENT SYSTEM PROMPT

The agent's core instructions should establish:

```text
You are a forex-card research and recommendation agent for Indian students.

Your job is to help the user choose a forex card based on their actual situation.

You must:
- understand the user's situation
- ask only necessary questions
- handle uncertain estimates
- use tools for factual information
- never invent card fees
- never invent supported currencies
- never invent application URLs
- use structured card data as the source of truth
- use deterministic recommendation results
- explain recommendations clearly
- disclose assumptions
- cite sources
- distinguish reference FX rates from provider rates
- never claim the recommendation is financial advice
```

Critical:

```text
Never make up missing financial-product information.
If a fact is unknown, say it is unknown.
```

---

# 39. AGENT BEHAVIOUR

The agent should NOT immediately call every tool.

Example:

User:

> I'm going to the UK for a master's.

Agent:

> Nice. Roughly how much do you expect to spend each month? An estimate is completely fine.

Then:

User:

> Maybe £1,000–£1,200.

Agent can infer:

- UK
- GBP
- student
- likely long-term stay
- spending range

Then ask only high-value missing questions.

---

# 40. AGENT RESEARCH WORKFLOW

When enough profile information exists:

```text
1. search_cards()
2. identify candidate cards
3. get_card_details() for candidates
4. identify missing/stale fields
5. research_card() where needed
6. get_fx_rate()
7. calculate_card_cost()
8. compare_cards()
9. get_card_sources()
10. formulate explanation
```

The agent should not research 30 cards if only 5 are relevant.

---

# 41. WEB RESEARCH

Use Amazon Bedrock Web Search where supported.

Web research is for:

- current fees
- product changes
- supported currencies
- application availability
- official provider information
- verification

Search queries should strongly prefer official domains.

Example:

```text
site:hdfcbank.com Regalia ForexPlus fees
site:axisbank.com forex card fees
site:icicibank.com forex prepaid card charges
```

The research tool must store:

```text
url
title
domain
retrieved_at
snippet/content
```

---

# 42. DATA VERIFICATION AGENT

Create a separate service/module for future automated verification:

```text
backend/app/verification/
```

It should be possible to run:

```text
verify_card(card_id)
```

Process:

```text
existing DB data
      ↓
official web research
      ↓
extract current facts
      ↓
compare with DB
      ↓
generate proposed changes
      ↓
flag changes
```

Do NOT automatically update production card data in the first version.

---

# 43. VERIFICATION CHANGE MODEL

Create:

```text
verification_runs
verification_changes
```

A change should record:

```text
card_id
field
old_value
new_value
source_id
confidence
status
created_at
```

status:

```text
pending
approved
rejected
```

Later an admin UI can approve these.

---

# 44. ADMIN ENDPOINTS

Create minimal internal endpoints:

```text
GET /admin/cards
GET /admin/cards/{id}
POST /admin/cards/{id}/verify
GET /admin/verification/changes
POST /admin/verification/changes/{id}/approve
POST /admin/verification/changes/{id}/reject
```

Protect them with an admin secret in v1.

Do not build a full admin dashboard unless time allows.

---

# 45. API DESIGN

## POST `/api/chat`

Request:

```json
{
  "session_id": "uuid",
  "message": "I'm going to the UK for my master's..."
}
```

Response should support streaming if practical.

Minimum response:

```json
{
  "session_id": "uuid",
  "message": "...",
  "profile": {},
  "recommendation": null,
  "tool_events": []
}
```

---

# 46. SESSION

No mandatory user account.

Use:

```text
session_id
```

Generate a UUID client-side/server-side.

Persist:

- messages
- profile
- recommendations
- tool events

---

# 47. DATABASE TABLES FOR SESSIONS

## sessions

```text
id
created_at
updated_at
```

## messages

```text
id
session_id
role
content
created_at
```

## user_profiles

```text
id
session_id
profile_json
updated_at
```

## recommendations

```text
id
session_id
recommended_card_id
recommendation_json
created_at
```

---

# 48. TOOL EVENTS

Store:

```text
id
session_id
tool_name
status
input_summary
output_summary
started_at
completed_at
```

Do not store unnecessary sensitive information.

---

# 49. FRONTEND CHAT

The frontend needs to support:

- normal conversational messages
- loading states
- tool activity
- structured recommendation result
- assumptions
- application CTA
- source links

Do not over-design.

Functional structure:

```text
Chat
  ↓
Agent activity
  ↓
Recommendation
  ↓
Cost explanation
  ↓
Alternatives
  ↓
Sources
  ↓
Apply
```

---

# 50. AGENT ACTIVITY UI

Expose real tool activity.

Example:

```text
Understanding your plans
✓ Destination: United Kingdom
✓ Estimated monthly spend: £1,000–£1,200

Researching forex cards
✓ Checking current card fees
✓ Checking GBP support

Checking today's FX rate
✓ GBP/INR reference rate retrieved

Calculating your expected costs
✓ 7 relevant cards compared

Finding your best match
✓ Recommendation ready
```

Do not fake these states.

They must correspond to actual backend events.

---

# 51. RECOMMENDATION UI DATA

The backend should return enough data for the frontend to render:

```text
provider
card_name
match_score
estimated_cost
currency
key_reasons[]
downsides[]
best_for[]
application_url
sources[]
last_verified
```

---

# 52. APPLICATION CTA

Primary CTA:

> Apply for this card

Open the provider URL in a new tab.

Do not attempt to reproduce provider KYC.

Before opening:

track:

```text
application_click
```

with:

```text
card_id
provider
session_id
source
```

Do not send unnecessary user information to analytics.

---

# 53. AFFILIATE SUPPORT

Application URLs should have:

```text
official_url
affiliate_url
```

Selection logic:

```python
if affiliate_url:
    use affiliate_url
else:
    use official_url
```

But:

**affiliate availability must NEVER influence recommendation score.**

---

# 54. ANALYTICS

Track:

```text
session_started
message_sent
profile_completed
recommendation_started
recommendation_generated
card_viewed
alternative_viewed
application_click
recommendation_recalculated
```

Optional:

```text
destination_country
top_card_id
```

Avoid collecting sensitive personal/financial data.

---

# 55. FINANCIAL SAFETY

Display:

> This is an informational comparison, not financial advice. Card fees and terms can change. Check the provider's current terms before applying.

This is especially important because card fees and rates can change.

---

# 56. DATA FRESHNESS

Every card fact should have:

```text
last_verified_at
```

Recommendation logic should flag stale information.

Suggested thresholds:

```text
< 7 days: fresh
7–30 days: recent
30–90 days: aging
> 90 days: stale
```

For the MVP, stale does not necessarily mean unusable.

But the agent should prefer fresh data.

---

# 57. STALE DATA BEHAVIOUR

If a key fee is stale:

The agent may research it again before recommending the card.

Example:

> I found this card in the database, but its ATM fee hasn't been verified recently, so I'm checking the provider's current information before comparing it.

---

# 58. UNKNOWN DATA

Never convert:

```text
unknown
```

to:

```text
0
```

If ATM fee is unknown:

```text
atm_fee = null
```

The scoring system must penalize uncertainty appropriately or exclude that component.

Do not falsely claim a card is cheaper because data is missing.

---

# 59. RECOMMENDATION CONFIDENCE

Return:

```text
high
medium
low
```

Confidence should depend on:

- completeness of card data
- freshness
- number of relevant sources
- quality of recommendation separation

Example:

If Card A and B differ by only £2/year:

```text
confidence = medium
```

Do not pretend there is a huge difference.

---

# 60. TIES

If cards are effectively tied:

Say:

> These two are effectively tied for your usage.

Do not force a winner through arbitrary decimal points.

---

# 61. SOURCE DISPLAY

Sources should include:

```text
Provider
Page title
URL
Last verified
```

Example:

```text
HDFC Bank — Regalia ForexPlus fees
Last verified: 8 Sep 2026
```

---

# 62. DATABASE SEED SCRIPT

Create:

```text
backend/scripts/seed_cards.py
```

It should:

1. create providers
2. create cards
3. create currencies
4. create fees
5. create limits
6. create benefits
7. create sources

Every seed fact must include a source.

Do not put unsourced values into seed data.

---

# 63. CARD DATA QUALITY

Create validation tests that fail if:

- active card has no application URL
- fee has no source
- currency record has no card
- fee has invalid currency
- source URL is invalid
- last_verified_at missing
- negative fee
- percentage outside valid range
- duplicate active card slug

---

# 64. API ERROR HANDLING

Use structured errors:

```json
{
  "error": {
    "code": "FX_PROVIDER_UNAVAILABLE",
    "message": "Live FX data is temporarily unavailable."
  }
}
```

Never expose:

- API keys
- stack traces
- AWS credentials
- internal SQL

---

# 65. FALLBACKS

If FX provider fails:

- retry
- use recently cached rate if available
- clearly mark it as cached

If web search fails:

- use verified database data
- mark research unavailable
- do not fabricate current information

If recommendation engine fails:

- return a controlled error
- do not let the LLM invent a recommendation

---

# 66. SECURITY

Never put:

- AWS keys
- API keys
- database credentials

in frontend code.

All secrets are backend-only.

Use `.env.example`.

Never commit `.env`.

---

# 67. ENVIRONMENT VARIABLES

Create:

```text
DATABASE_URL=
AWS_REGION=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
BEDROCK_MODEL_ID=
POSTHOG_API_KEY=
POSTHOG_HOST=
SENTRY_DSN=
FX_PROVIDER=
FX_API_KEY=
ADMIN_SECRET=
```

Only variables actually required by the implementation should be used.

---

# 68. LOCAL DEVELOPMENT

Root structure:

```text
/
├── frontend/
├── backend/
├── docs/
├── scripts/
├── docker-compose.yml
├── README.md
├── BUILD.md
├── LICENSE
└── .gitignore
```

---

# 69. BACKEND STRUCTURE

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db/
│   │   ├── session.py
│   │   ├── base.py
│   │   └── models/
│   ├── api/
│   │   ├── chat.py
│   │   ├── cards.py
│   │   ├── recommendations.py
│   │   └── admin.py
│   ├── agent/
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── tools/
│   ├── recommendation/
│   ├── fx/
│   ├── research/
│   ├── verification/
│   ├── analytics/
│   └── schemas/
├── migrations/
├── scripts/
├── tests/
├── pyproject.toml
└── Dockerfile
```

---

# 70. FRONTEND STRUCTURE

```text
frontend/
├── app/
│   ├── page.tsx
│   ├── chat/
│   └── api/
├── components/
│   ├── chat/
│   ├── recommendation/
│   ├── sources/
│   └── activity/
├── lib/
│   ├── api.ts
│   ├── analytics.ts
│   └── types.ts
├── public/
├── package.json
└── tsconfig.json
```

---

# 71. DO NOT OVERBUILD UI

For now:

- clean
- functional
- responsive
- readable

Do not spend hours on:

- animations
- elaborate branding
- custom illustrations
- complex landing page
- perfect typography
- fancy gradients

The product owner will handle design later.

---

# 72. CHAT STREAMING

If practical, implement streaming.

Preferred experience:

```text
Agent thinking/researching
↓
tool event
↓
agent response
```

If streaming creates excessive complexity, first implement reliable request/response and then add streaming.

Reliability comes first.

---

# 73. AGENTCORE

Prepare the agent so it can be deployed to Amazon Bedrock AgentCore Runtime.

Use the official AgentCore runtime approach.

Keep the core agent callable through a normal Python function.

Example conceptual interface:

```python
def run_agent(session_id: UUID, message: str) -> AgentResponse:
    ...
```

Then wrap it for:

- FastAPI
- AgentCore

Do not tightly couple the business logic to AgentCore.

---

# 74. AGENTCORE DEPLOYMENT

Create:

```text
agentcore/
```

containing the required deployment configuration.

Document:

```text
agentcore dev
agentcore deploy
agentcore invoke
```

if using the AgentCore CLI.

Do not block local development on AgentCore deployment.

---

# 75. MODEL ABSTRACTION

Create a model configuration layer.

Default:

```text
BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-6
```

But the agent implementation must not hard-code the model.

The project should be capable of changing providers later.

---

# 76. DATABASE MIGRATIONS

Use Alembic.

Commands:

```bash
alembic upgrade head
```

Seed:

```bash
python scripts/seed_cards.py
```

---

# 77. DOCKER COMPOSE

Provide local:

```text
postgres
```

Optionally:

```text
redis
```

Only include Redis if actually used.

The frontend/backend may run outside Docker during development.

---

# 78. TESTING

Minimum backend tests:

### Profile

- extract destination
- extract spending range
- update profile
- handle unknown values

### Cost

- issuance fee
- reload fee
- ATM fee
- cross-currency fee
- zero fees
- missing fees
- multiple months

### Ranking

- lowest-cost card wins when cost is dominant
- ATM-heavy user favours low ATM fee
- rewards-heavy user favours rewards
- currency mismatch penalized
- weights normalized
- ties handled

### Data

- source required
- stale data detection
- invalid fees rejected

### API

- chat endpoint
- recommendation endpoint
- error handling

---

# 79. FRONTEND TESTS

At minimum test:

- chat sends message
- loading state
- tool activity rendering
- recommendation renders
- application CTA
- assumptions display
- error state

---

# 80. END-TO-END DEMO SCENARIO

The application MUST support this scenario:

User says:

> I'm an Indian student going to the UK for a two year master's. I'll probably spend around £1,000 to £1,200 a month. I won't withdraw much cash. I mainly care about keeping fees low.

Agent should:

1. understand UK
2. understand student context
3. understand two-year duration
4. understand £1,000–£1,200 estimate
5. understand low ATM usage
6. understand cost priority
7. ask only useful missing questions
8. search relevant cards
9. verify important current data
10. retrieve GBP/INR reference rate
11. calculate estimated costs
12. rank cards
13. return top 3
14. explain winner
15. explain alternatives
16. show sources
17. show application button

This scenario must work reliably before considering the MVP complete.

---

# 81. SECOND DEMO SCENARIO

After receiving a recommendation, user says:

> Actually I think I'll withdraw cash twice a week.

The system must:

1. update ATM assumptions
2. recalculate
3. rerank
4. explain what changed

---

# 82. THIRD DEMO SCENARIO

User says:

> I don't really care about fees. I want rewards and airport lounge benefits.

The system must change preference weights and rerank.

---

# 83. IMPORTANT: NO FAKE DATA

The application must never say:

> Current fee: ₹0

unless the database contains verified evidence that the fee is ₹0.

Likewise:

- no invented rewards
- no invented application URLs
- no invented currencies
- no invented limits

Unknown is better than wrong.

---

# 84. RESEARCH DATA PIPELINE

Build the system so that future automation can work like this:

```text
Scheduled verification
        ↓
Select stale cards
        ↓
Research official source
        ↓
Extract facts
        ↓
Compare with DB
        ↓
Create verification changes
        ↓
Admin approval
        ↓
Publish updated data
```

Do not implement a full scheduler unless time allows.

The data model must support it.

---

# 85. FUTURE EXTENSIBILITY

Do not build these now, but avoid architecture that prevents them:

- affiliate tracking
- more forex cards
- student bank accounts
- international remittance
- international insurance
- tuition payment services
- multi-product financial recommendations
- user accounts
- saved recommendations
- price/fee change alerts

The current product remains forex cards only.

---

# 86. PRIVACY

Do not collect:

- passport number
- bank account number
- card number
- Aadhaar
- PAN
- KYC documents

The app does not need them.

User profile should contain only information required for comparison.

---

# 87. FINANCIAL DATA DISCLAIMER

The application should make clear:

> Fees, exchange rates and product terms can change. Always verify the provider's current terms before applying.

And:

> This comparison is informational and is not financial advice.

---

# 88. OBSERVABILITY

Log:

```text
request_id
session_id
tool_name
duration
success/failure
model latency
recommendation latency
FX provider latency
research latency
```

Never log secrets or unnecessary personal data.

---

# 89. AGENT TRACEABILITY

For hackathon demo purposes, make tool execution observable.

A judge should be able to see:

```text
search_cards
↓
research_card
↓
get_fx_rate
↓
calculate_card_cost
↓
compare_cards
```

This is important.

The agent must visibly perform work.

---

# 90. README

Create a strong README containing:

## Product

What ForexMatch does.

## Problem

Why students struggle to choose forex cards.

## Solution

How the agent researches and compares them.

## Architecture

Diagram.

## Agent

Explain Strands usage.

## Tools

List agent tools.

## Recommendation engine

Explain deterministic ranking.

## Data trust

Explain sources and verification.

## Running locally

Exact commands.

## Environment variables

Exact configuration.

## Deployment

AWS/AgentCore instructions.

## Testing

Commands.

## Hackathon

Mention the Agents for Humans Hackathon.

---

# 91. ARCHITECTURE DIAGRAM

Create:

```text
docs/architecture.md
```

and optionally:

```text
docs/architecture.png
```

Diagram should show:

```text
User
 ↓
Next.js
 ↓
FastAPI
 ↓
Strands Agent
 ├── PostgreSQL
 ├── Web Search
 ├── FX Service
 ├── Cost Calculator
 └── Recommendation Engine
 ↓
Application Provider
```

Also show optional:

```text
AgentCore Runtime
```

---

# 92. LICENSE

Use MIT.

Create:

```text
LICENSE
```

---

# 93. GIT

Keep a clean commit history.

Recommended commits:

```text
initial project setup
database schema
card data model
recommendation engine
fx service
strands agent
agent tools
chat api
frontend chat
recommendation UI
verification pipeline
analytics
tests
deployment
documentation
```

Do not squash everything into one giant commit.

---

# 94. CODE QUALITY

Prefer:

- typed Python
- Pydantic models
- small services
- dependency injection
- explicit interfaces
- unit tests
- clear error handling

Avoid:

- giant files
- global mutable state
- hard-coded card logic
- hidden business rules
- LLM-generated calculations
- duplicated fee logic

---

# 95. RECOMMENDATION ENGINE MUST BE PURE

Ideally:

```python
recommend(
    user_profile,
    cards,
    fx_rates
) -> RecommendationResult
```

The function should be deterministic.

Same input:

```text
same output
```

This makes it testable.

---

# 96. AGENT VS APPLICATION LOGIC

Agent:

```text
"What information do I need?"
"Which tools should I call?"
"How should I explain this?"
```

Application:

```text
"What does this fee cost?"
"Which card scores highest?"
"What is the expected annual cost?"
```

Never mix these responsibilities unnecessarily.

---

# 97. APPLICATION FLOW

The application should NOT claim:

> "Your card has been ordered."

It has not.

Instead:

> "Apply for this card"

and open the official/affiliate application flow.

Track the click.

---

# 98. AFFILIATE DISCLOSURE

If affiliate links are used:

Display a concise disclosure somewhere appropriate:

> We may earn a commission if you apply through some links. This does not affect our rankings.

This must remain true.

---

# 99. PRODUCT PHILOSOPHY

The key differentiator is trust.

The product should feel like:

> "This agent actually researched this for me."

Not:

> "ChatGPT gave me a random card."

Therefore prioritize:

1. current data
2. sources
3. calculations
4. personalized assumptions
5. transparent ranking
6. agent tool execution

over:

1. flashy animations
2. generic AI copy
3. unnecessary features

---

# 100. MVP DEFINITION OF DONE

The MVP is complete only when:

### User

- [ ] Can open site
- [ ] Can start conversation
- [ ] Can describe study-abroad plans naturally
- [ ] Agent extracts profile
- [ ] Agent asks useful follow-ups
- [ ] User can give approximate values
- [ ] User can state priorities

### Agent

- [ ] Uses Strands Agents SDK
- [ ] Calls custom tools
- [ ] Uses card database
- [ ] Can research current information
- [ ] Can get FX rate
- [ ] Can invoke recommendation engine
- [ ] Can explain result

### Data

- [ ] 15–30 real cards/products
- [ ] Sources attached
- [ ] Last verified dates
- [ ] No fabricated fees
- [ ] No fabricated URLs

### Recommendation

- [ ] Deterministic
- [ ] Personalized
- [ ] Weighted preferences
- [ ] Cost calculation
- [ ] ATM calculation
- [ ] Currency suitability
- [ ] Top 3 results
- [ ] Alternatives
- [ ] Assumptions
- [ ] Sources

### Product

- [ ] Application CTA
- [ ] Application click tracking
- [ ] Re-ranking works
- [ ] Error states work
- [ ] No mandatory login

### Engineering

- [ ] PostgreSQL
- [ ] Alembic migrations
- [ ] API tests
- [ ] Recommendation tests
- [ ] Data validation
- [ ] README
- [ ] Architecture diagram
- [ ] MIT license
- [ ] `.env.example`
- [ ] Docker/local setup
- [ ] AWS deployment path
- [ ] AgentCore deployment path if practical

---

# 101. PRIORITY ORDER

If time becomes limited, implement in this exact order:

## P0 — MUST WORK

1. PostgreSQL
2. card schema
3. verified seed cards
4. deterministic recommendation engine
5. cost calculator
6. FX service
7. Strands agent
8. agent tools
9. FastAPI chat endpoint
10. Next.js chat
11. recommendation result
12. application links
13. sources

## P1 — SHOULD WORK

14. streaming
15. visible tool activity
16. re-ranking
17. analytics
18. verification workflow
19. AgentCore deployment
20. tests

## P2 — NICE TO HAVE

21. admin UI
22. advanced animations
23. user accounts
24. saved recommendations
25. automated scheduled verification

Do NOT sacrifice P0 functionality for P2 features.

---

# 102. FINAL DEMO FLOW

The final product demonstration should look approximately like:

```text
User:
"I'm going to the UK for a 2 year master's..."

Agent:
"Got it. Roughly how much do you expect to spend each month?"

User:
"Probably £1,000–£1,200."

Agent:
"That's enough to work with. How often do you expect to use cash?"

User:
"Maybe once or twice a month."

Agent:
[tool activity]

Understanding your plans ✓
Researching relevant cards ✓
Checking current fees ✓
Checking GBP support ✓
Checking today's FX rate ✓
Calculating expected costs ✓
Comparing 8 relevant cards ✓

Agent:
"Based on your usage, I'd go with X..."

Result:
X
Estimated cost
Why it fits
What could make Y better
Sources
Last verified
Apply

User:
"Actually I might use cash more."

Agent:
[recalculates]

"The ranking changes because ATM fees now matter more..."

New recommendation
```

This is the core experience.

---

# 103. DO NOT BUILD

Do not build:

- banking transactions
- card issuance
- KYC
- payment processing
- actual forex purchases
- bank account opening
- remittance
- crypto
- credit cards
- loans
- investment products
- financial advice engine
- mandatory authentication
- mobile app
- complex admin dashboard

Those are future products.

---

# 104. FINAL ENGINEERING INSTRUCTION

Build this as if it will become a real startup after the hackathon.

Do not build a disposable hackathon demo.

At the same time, do not over-engineer features that aren't required.

The most important thing is that the following loop genuinely works:

```text
USER
 ↓
STRANDS AGENT
 ↓
UNDERSTAND REQUIREMENTS
 ↓
RESEARCH CURRENT CARD DATA
 ↓
GET FX RATE
 ↓
DETERMINISTIC CALCULATION
 ↓
PERSONALIZED RANKING
 ↓
EXPLAIN
 ↓
APPLICATION
```

If a choice is not specified in this document:

1. prefer the simplest production-quality solution
2. preserve the architecture above
3. avoid introducing a new dependency unless necessary
4. prefer official provider data
5. never invent financial information
6. keep the recommendation engine deterministic
7. keep the agent responsible for orchestration and explanation

Start by creating the repository structure and database schema, then implement the backend core, then the Strands agent, then the frontend, then testing/deployment.

Do not stop at scaffolding.

The goal is a working end-to-end product.