# Architecture

## The shape of the system

```mermaid
flowchart TD
    User([Student])
    Next["Next.js frontend<br/>chat · activity feed · recommendation"]
    API["FastAPI backend"]
    Agent["Strands agent<br/>conversation · tool selection · explanation"]
    Engine["Recommendation engine<br/>deterministic · pure"]
    DB[("PostgreSQL<br/>cards · sources · sessions · verification")]
    FX["FX service<br/>reference rates, cached"]
    Search["Bedrock web search"]
    Provider([Provider application page])
    Core["Bedrock AgentCore Runtime<br/>(optional deployment target)"]

    User -->|message| Next
    Next -->|HTTPS / SSE| API
    API --> Agent
    Agent -->|tools| DB
    Agent -->|tools| FX
    Agent -->|tools| Search
    Agent -->|compare_cards| Engine
    Engine --> DB
    Engine --> FX
    Engine -->|ranking| Agent
    Agent -->|explanation| API
    API -->|tool events, result| Next
    Next -->|tracked click| Provider
    Agent -.-> Core

    style Engine stroke-width:3px
    style Agent stroke-width:3px
```

The two thick boxes are the ones that matter, and the split between them is the
whole design: the **agent** decides what to do and how to explain it, the
**engine** decides what things cost and which card wins.

## The pipeline

```
Natural language
      ↓  Strands agent
Structured UserProfile
      ↓  search_cards / get_card_details / research_card
Verified card data (with sources)
      ↓  get_fx_rate
Reference rates
      ↓  calculate_card_cost      ← deterministic
Expected cost per card
      ↓  compare_cards            ← deterministic
Ranked result + confidence
      ↓  Strands agent
Explanation
      ↓
Recommendation UI → Apply
```

What never happens:

```
User message → LLM → "I think HDFC is best"
```

## Why the engine is a pure function

`recommend(profile, cards, fx) -> RecommendationResult` performs no I/O, holds
no state and calls no model. That buys three things:

- **Testability.** Ranking rules are asserted against hand-built fixtures, with
  no database or network in the way.
- **Reproducibility.** The same inputs always produce the same ranking, so a
  result can be explained after the fact.
- **A hard boundary.** The model is handed the ranking as a fact to explain. It
  has no route to change it, because the function that produced it does not
  take a model.

The service layer (`app/recommendation/service.py`) is the only place that
translates database rows into the engine's frozen `CardFacts` snapshots.

## Data flow for one turn

```mermaid
sequenceDiagram
    participant U as Student
    participant F as Frontend
    participant A as FastAPI
    participant G as Strands agent
    participant T as Tools
    participant E as Engine

    U->>F: "UK, two years, £1,000–1,200, low cash"
    F->>A: POST /api/chat/stream
    A->>G: run the turn
    G->>T: update_user_profile
    T-->>F: tool event (streamed immediately)
    G->>T: search_cards
    T-->>F: tool event
    G->>T: get_fx_rate
    T-->>F: tool event
    G->>T: compare_cards
    T->>E: recommend(profile, cards, fx)
    E-->>T: ranked result
    T-->>F: tool event
    G-->>F: explanation (streamed text)
    A-->>F: profile, recommendation, done
```

Each tool event is written to `tool_events` as it happens and streamed in the
same moment. The activity feed is a view of that table — there is no code path
that emits an event the agent did not cause.

## Handling missing data

The catalogue distinguishes three states that are easy to conflate and
expensive to get wrong:

| State | Meaning | How it is priced |
| --- | --- | --- |
| `is_waived` | The provider states the charge is nil | ₹0, and shown as free |
| `is_unknown` | The provider publishes no figure | Imputed at the worst figure among the compared cards, flagged |
| `amount IS NULL` | Not verified | Same as unknown |

Costing runs over the whole candidate set rather than card by card, precisely so
that a missing component can be filled from what competitors charge. Where no
card in the set publishes a charge, it is dropped and the total is labelled a
lower bound.

The rule this enforces: **a card can never rank better because its issuer
published less.**

## Verification

```
Stale card  →  research official sources  →  extract  →  compare with DB
                                                             ↓
                                                    verification_changes
                                                       (status: pending)
                                                             ↓
                                                     admin approval
                                                             ↓
                                                     published data
```

The first version never writes to the catalogue automatically. A misread fee
that reaches a student is worse than a stale one, so a human sits in the loop.

## Deployment

```mermaid
flowchart LR
    subgraph Client
      B[Browser]
    end
    subgraph AWS
      FE["Frontend<br/>(static / Node)"]
      BE["FastAPI container<br/>ECS, App Runner or Lambda"]
      PG[("RDS PostgreSQL")]
      BR["Bedrock"]
      AC["AgentCore Runtime<br/>(optional)"]
    end
    B --> FE --> BE
    BE --> PG
    BE --> BR
    AC -.-> PG
    AC -.-> BR
```

The backend stays a conventional FastAPI application whether or not AgentCore is
used; `agentcore/entrypoint.py` is a thin adapter over the same `run_agent`
callable, so neither deployment target is privileged.
