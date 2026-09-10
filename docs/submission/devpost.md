# Devpost submission — ForexMatch

## Tagline (one line)

An agent that reads the forex-card fee schedules so Indian students don't have to — and
shows every figure it used.

## Elevator pitch (Devpost's short field, ~200 characters)

Choosing a forex card costs Indian students real money. ForexMatch's agent reads the
providers' published fees, prices every card against your actual spending, and shows its
working. No commission.

---

## Inspiration

Every year a very large number of Indian students move abroad for university, and almost
all of them buy a forex card before they fly. It is often the first serious financial
product they choose alone, usually in the fortnight before departure, usually on a
friend's recommendation.

It is a genuinely hard comparison. The cost is spread across issuance, reloads, ATM
withdrawals and cross-currency charges; the figures live in different documents, quoted
in different currencies; and some providers simply do not publish parts of it. The
comparison sites that exist are mostly ranked by commission.

The gap between the best and worst card in our catalogue, for a two-year master's in the
UK, is over a lakh of rupees. That is a meaningful amount of money to a student, and it
is decided by a choice made in an afternoon with bad information.

## What it does

You tell ForexMatch where you are going and roughly how you will spend — either through
six questions or by describing it in your own words. It then:

- searches a catalogue of real forex products
- reads each candidate's **published** fees
- fetches today's mid-market reference rate
- prices every card against your expected usage — issuance, reloads, ATM withdrawals,
  cross-currency conversion
- ranks them by weights you set, and explains the winner, the alternatives, and what
  would change the answer

Two things it deliberately does **not** do: it never lets the language model choose the
winner, and it never treats an unpublished fee as zero.

Everything is shown: the arithmetic, the assumptions it made about you, the exchange
rate it used, the cards it ruled out and why, and a link to the provider's own fee
schedule with the date we last checked it.

There is no login, no email capture, and no commission from any provider.

## How we built it

**The agent** is built on the **Strands Agents SDK**, running **Claude Sonnet 4.6 on
Amazon Bedrock**. It has ten narrow custom tools — get and update the user profile,
search the catalogue, fetch card details, research a provider, get an FX rate, calculate
a card's cost, compare cards, fetch application links, fetch sources. Every invocation is
timed and recorded, and the activity feed in the UI renders those records directly, so
what you watch is what actually ran.

**The recommendation engine** is a pure Python function: `recommend(profile, cards, fx)`.
No I/O, no model call, no randomness. It hard-filters unsuitable cards, prices the rest,
scores six weighted components, detects ties and grades its own confidence from data
completeness, freshness, source count and the margin between the top two.

**The data** is 16 real products from 7 Indian providers, 346 individually sourced facts
in PostgreSQL. Every fee, limit, benefit and currency row carries a NOT NULL source id —
it is structurally impossible to store an unsourced financial fact. Money columns are
nullable, and NULL means *not verified*, never zero.

**Deployment**: Next.js frontend and FastAPI backend both on Vercel, PostgreSQL on Neon,
Bedrock reached through **OIDC federation** so no long-lived AWS credentials exist
anywhere — the function exchanges a short-lived deployment token for temporary
credentials scoped to `bedrock:InvokeModel` on Anthropic models and nothing else.

207 tests, CI on every push.

## Challenges we ran into

**Providers that block automated reading.** Some banks' pages are behind bot protection.
Rather than guess, those cards carry a note recording that their figures need
re-verification, and the card page says so.

**Concurrent tool calls corrupting the audit trail.** Strands runs a turn's tools in
parallel, and they all shared one async database session — which is not safe. Interleaved
flushes lost row identity, so each tool event was inserted twice, once stranded at
"started". A real Bedrock turn produced 16 rows for 10 calls. It mattered more than a
stray row: the panel whose entire purpose is showing what the agent really did was
showing phantom work.

**A waived fee is not a free conversion.** While preparing the demo, a US-dollar-only
card was winning for a UK student at ₹0 — because the provider advertises "zero
cross-currency fees". But that is a claim about their *fee*, not their *rate*. Spend
pounds on a dollar card and every purchase is still converted at a spread nobody
publishes. Pricing that at zero was the same mistake as reading an unpublished fee as
nil. Fixed, and that card now ranks 32nd rather than 1st.

**Getting the OIDC token.** Vercel delivers it as an environment variable during builds
but as a per-request header inside a function — and the documented helper is
JavaScript-only. The first deployment failed with `NoCredentialsError` until we read the
header instead.

## Accomplishments we're proud of

The **honesty machinery**, which is the part we would defend hardest:

- An unpublished fee is imputed with the *worst* charge among the compared cards, that
  line is labelled, and the total is flagged as a lower bound. A card can never look
  cheap because its issuer was quiet.
- The distinction between "the provider states this is nil" and "the provider publishes
  no figure" is preserved from the database schema all the way to the pixel.
- A mid-market reference rate is never presented as the rate a provider will give you.
- Confidence is graded and explained, and it is frequently *medium* or *low* — because
  that is the truth about the underlying data.

And the architecture: the model runs the conversation, code decides the answer. There is
a test asserting that an unpublished fee cannot make a card rank cheaper.

## What we learned

That the interesting problem in an agent product is not getting the model to answer — it
is deciding what the model is *not allowed* to do. Almost every bug worth fixing here was
a place where an unknown had quietly become a number.

Also that building the demo is a debugging technique. Two of the three most significant
bugs surfaced while clicking through the product as a user rather than while writing it.

## What's next

- Widening the catalogue, and verifying the currency lists that are still unconfirmed —
  which is what currently drags several results to low confidence
- Turning on Bedrock's web search so the verification pipeline can re-check fee schedules
  on a schedule and raise proposed changes for human approval; the data model and admin
  endpoints for that already exist
- Cost-of-living-aware spend estimation beyond the current per-destination bands
- More destinations, and non-student travellers

## Built with

`strands-agents` · `amazon-bedrock` · `claude-sonnet-4.6` · `python` · `fastapi` ·
`sqlalchemy` · `alembic` · `postgresql` · `neon` · `asyncpg` · `pydantic` · `next.js` ·
`react` · `typescript` · `tailwindcss` · `vercel` · `aws-oidc` · `pytest` · `vitest`

## Links

- **Live demo**: https://forexmatch.vercel.app
- **API**: https://forexmatch-api.vercel.app
- **Repository**: https://github.com/shlokpanjabi/forexmatch (MIT)
- **Architecture**: https://github.com/shlokpanjabi/forexmatch/blob/main/docs/architecture.md
- **Data policy & verification dates**: https://forexmatch.vercel.app/terms

## Track

**Everyday Agents** — a personal money decision most students make once, badly, under
time pressure. Read the other two track descriptions before submitting; if Everyday
looks like a poor fit, the verification pipeline (a background agent that re-checks fee
schedules and surfaces proposed changes for human approval) is the angle to lead with.
