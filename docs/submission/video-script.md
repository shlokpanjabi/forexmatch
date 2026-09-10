# ForexMatch — demo video script

**Target: 4 min 30 s (hard limit 5:00). No face needed — screen recording plus voiceover.**

Record at 1280×800 or larger, dark room, browser zoom ~110% so text is legible after
compression. Have the live site open and the backend warm (hit the API once first, so
the first agent turn isn't waiting on a cold start).

Judging weights presentation equally with everything else, and the criterion is *"does
the video clearly demonstrate the project working end-to-end"* — so the demo runs before
the architecture, and nothing is claimed that isn't shown.

---

## 0:00 – 0:35 · The problem

> **On screen:** a provider's fee schedule PDF, scrolled — dense per-currency tables.

"Every year, hundreds of thousands of Indian students move abroad, and almost all of
them need a forex card before they go.

Choosing one is genuinely hard. The fees are split across issuance, reloads, ATM
withdrawals and cross-currency charges. They're published in different places, in
different currencies, and some providers don't publish them at all.

So students pick on a friend's recommendation, or on whichever comparison site ranked
highest — and those sites are usually ranked by commission.

The cost of getting it wrong is real: on a two-year master's, the gap between the best
and worst card in our catalogue is over a lakh of rupees."

---

## 0:35 – 1:05 · What it is

> **On screen:** the ForexMatch landing page. Scroll slowly through the hero.

"ForexMatch is an agent that does the comparison properly.

You tell it where you're going and roughly how you'll spend. It reads the providers'
own published fee schedules, prices every card against your actual usage, and shows you
every figure it used and where it came from.

It takes no commission from anyone. And crucially — the language model never decides
which card wins."

---

## 1:05 – 2:00 · Demo one: the fast path

> **On screen:** click **Find my card**. Move briskly — one question per screen.

"There are two ways in. The quick one is six questions."

> UK → Two years → £900–£1,300 → Rarely → Mostly one country → Keeping fees low.
> **Pause on the spend screen.** "Notice these bands are in pounds, and they're sized
> for the UK — pick the UAE and they're in dirhams, sized for Dubai."

> **Result appears.**

"About a second, because no model is involved in this path — it goes straight to the
ranking engine.

Top match: the WSFx GlobalPay card at 94%, about ₹7,200 in fees over two years. Axis is
effectively tied at ₹7,066 — and it says they're tied, rather than inventing a winner
out of a decimal point.

Every eligible card is ranked, not just a top three."

> **Expand the winner's calculation.**

"And the full arithmetic is here: issuance, twenty-four reloads, twenty-four ATM
withdrawals, cross-currency — with the exchange rate used, the assumptions we made
about you, and a link to the provider's own fee schedule with the date we checked it."

---

## 2:00 – 2:50 · Demo two: the agent

> **On screen:** open **/chat**, click the first example prompt.

"The other way in is just describing your situation."

> Let it run. **Do not cut the activity feed** — this is the core of the submission.

"This is the agent working. Every line is a real tool call — it's understanding the
plans, searching the catalogue, reading five cards' published fees, fetching today's
GBP/INR reference rate, then running the comparison. Those are timings from the actual
calls, not an animation.

It chose that sequence itself. It wasn't scripted."

> **When the answer arrives, scroll to the caveat.**

"And here's the part I'd point at. It says BookMyForex doesn't publish its ATM charge,
so the engine substituted the highest fee among the compared cards — and it tells you to
ask them directly before applying.

It volunteered that. Nobody asked it to."

> **Type:** *"Actually I care more about rewards than fees."*

"Change your mind and it re-weights and re-ranks — same session, no starting over."

---

## 2:50 – 3:40 · The two ideas that matter

> **On screen:** the /about page, the six pipeline steps with their agent/code tags.

"Two design decisions make this different from asking a chatbot which card is best.

**First: the model orchestrates, code decides.** Claude runs the conversation, picks the
tools and writes the explanation. But every fee, every calculation and the ranking
itself come from deterministic Python. The model structurally *cannot* choose a
different winner or nudge a score. Same inputs, same output — and there are tests that
prove it.

**Second: unknown is never zero.**"

> **On screen:** a card page showing "Not published" in amber next to "Nil" in green.

"Some providers don't publish every charge. Treating a blank as a zero would reward the
issuers who disclose least — so we don't. An unpublished fee is recorded as unknown, and
when we price that card we substitute the *highest* charge among its competitors, label
that line, and flag the total as a lower bound.

That principle caught a real bug while I was preparing this video. A US-dollar-only card
was winning for a UK student at zero fees — because the provider advertises 'zero
cross-currency fees'. But that's a claim about their fee, not their exchange rate. Spend
pounds on a dollar card and every purchase is still converted at a spread they don't
publish. That card now ranks 32nd instead of 1st."

---

## 3:40 – 4:15 · How it's built

> **On screen:** the architecture diagram, then a quick scroll of the tools directory.

"It's built on the Strands Agents SDK with Claude Sonnet 4.6 on Amazon Bedrock, reached
through OIDC federation so there are no long-lived AWS keys anywhere.

Ten custom Strands tools: profile, catalogue search, card details, research, FX rates,
the cost calculator, the comparison engine, application links and sources. Each one is
narrow and each one records what it did — which is what the activity feed reads.

Behind it, a Postgres catalogue of sixteen real products from seven Indian providers,
three hundred and forty-six individually sourced facts, every one carrying the document
it came from and the date it was verified.

Two hundred and seven tests, including one asserting that an unpublished fee can never
make a card rank cheaper."

---

## 4:15 – 4:30 · Close

> **On screen:** back to the landing page.

"It's live now at forexmatch.vercel.app — no login, nothing to install.

The point isn't that an agent can answer a question about forex cards. It's that an
agent can do the work, show you all of it, and be honest about what it doesn't know.

That's ForexMatch. Thanks for watching."

---

## Recording checklist

- [ ] Warm the API first — one request before recording, so no cold start on camera
- [ ] Confirm the top result is a GBP-wallet card, not the USD one (fixed, but re-check)
- [ ] Hide bookmarks bar; close other tabs
- [ ] Record system audio off; voiceover separately if easier
- [ ] Keep the activity feed uncut — it is the strongest 20 seconds in the video
- [ ] Export 1080p, upload to YouTube as **public** (not unlisted — rules say public)
