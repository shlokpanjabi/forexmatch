#!/usr/bin/env bash
# End-to-end smoke test against a running ForexMatch API.
#
#   ./deploy/smoke-test.sh                       # http://localhost:8000
#   ./deploy/smoke-test.sh https://your-api-url  # a deployment
#
# Checks the paths a user actually travels, plus the guarantees that matter:
# structured errors, a locked admin surface, sources on every card, and no fee
# that is silently zero.
set -uo pipefail

BASE="${1:-http://localhost:8000}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PASS=0
FAIL=0

# Response bodies go to files; Python reads the file. Interpolating JSON into a
# shell-quoted Python string breaks the moment a response contains a quote.
report() {
  local name="$1" result="$2"
  if [[ "$result" == PASS* ]]; then
    printf '  \033[32m✓\033[0m %-50s %s\n' "$name" "${result#PASS }"
    PASS=$((PASS + 1))
  else
    printf '  \033[31m✗\033[0m %-50s %s\n' "$name" "${result#FAIL }"
    FAIL=$((FAIL + 1))
  fi
}

# check <name> <file> <python body using `d` and printing PASS.../FAIL...>
check() {
  local name="$1" file="$2" body="$3"
  local out
  out=$(python3 - "$file" <<PY 2>&1
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as exc:
    print("FAIL unreadable response: %s" % exc); raise SystemExit
$body
PY
)
  report "$name" "$out"
}

# status <name> <url> <expected code> [<expected error code>]
status() {
  local name="$1" url="$2" want="$3" wantcode="${4:-}"
  local code body
  body=$(curl -s -o "$WORK/err.json" -w '%{http_code}' --max-time 20 "$url" 2>/dev/null)
  code="$body"
  if [[ "$code" != "$want" ]]; then
    report "$name" "FAIL got HTTP $code, expected $want"
    return
  fi
  if [[ -n "$wantcode" ]]; then
    check "$name" "$WORK/err.json" "
got = (d.get('error') or {}).get('code')
print('PASS %s' % got if got == '$wantcode' else 'FAIL error code %s' % got)"
  else
    report "$name" "PASS HTTP $code"
  fi
}

echo "ForexMatch smoke test → $BASE"

# --- Service ----------------------------------------------------------------
echo
echo "Service"
curl -s --max-time 15 "$BASE/health" -o "$WORK/health.json"
check "health endpoint reports ok" "$WORK/health.json" "
print('PASS model=%s fx=%s' % (d.get('model_provider'), d.get('fx_provider'))
      if d.get('status') == 'ok' else 'FAIL not ok')"

curl -s --max-time 15 "$BASE/" -o "$WORK/root.json"
check "root carries the financial disclaimer" "$WORK/root.json" "
print('PASS' if 'not financial advice' in (d.get('disclaimer') or '') else 'FAIL missing')"

# --- Catalogue --------------------------------------------------------------
echo
echo "Catalogue"
curl -s --max-time 20 "$BASE/api/cards" -o "$WORK/cards.json"
check "catalogue is populated" "$WORK/cards.json" "
n = d.get('count', 0)
print('PASS %d cards' % n if n >= 10 else 'FAIL only %d' % n)"

SLUG=$(python3 -c "
import json
d = json.load(open('$WORK/cards.json'))
print((d.get('cards') or [{}])[0].get('slug', ''))
" 2>/dev/null)

if [[ -n "$SLUG" ]]; then
  curl -s --max-time 20 "$BASE/api/cards/$SLUG" -o "$WORK/card.json"
  check "card detail carries fees and sources" "$WORK/card.json" "
f, s = len(d.get('fees') or []), len(d.get('sources') or [])
print('PASS %d fees, %d sources' % (f, s) if f and s else 'FAIL fees=%d sources=%d' % (f, s))"
  check "no fee is silently zero" "$WORK/card.json" "
bad = [x for x in (d.get('fees') or [])
       if x.get('amount') not in (None, '') and float(x['amount']) == 0 and not x.get('is_waived')]
print('PASS' if not bad else 'FAIL %d zero fees not marked waived' % len(bad))"
fi

status "unknown card returns a structured 404" "$BASE/api/cards/definitely-not-a-card" 404 NOT_FOUND

# --- Recommendation ---------------------------------------------------------
echo
echo "Recommendation engine"
curl -s --max-time 90 -X POST "$BASE/api/recommendations" \
  -H 'Content-Type: application/json' -o "$WORK/rec.json" \
  -d '{"profile":{"destination_country":"United Kingdom","destination_currencies":["GBP"],
       "trip_duration_months":24,
       "monthly_spend":{"min_amount":"1000","max_amount":"1200","currency":"GBP"},
       "atm_usage":"low","student_status":true}}'

check "returns a ranked recommendation" "$WORK/rec.json" "
c = d.get('recommended_card')
print('PASS %s (%s%%) INR %s' % (c['card']['card_name'], c['match_score'], c['estimated_cost']['total_inr'])
      if c else 'FAIL none returned')"
check "cost breakdown shows its working" "$WORK/rec.json" "
comp = ((d.get('recommended_card') or {}).get('estimated_cost') or {}).get('components') or []
print('PASS %d line items' % len(comp) if comp else 'FAIL no components')"
check "every quoted figure has a source" "$WORK/rec.json" "
s = len(d.get('sources') or [])
print('PASS %d sources' % s if s else 'FAIL none')"
check "assumptions are disclosed" "$WORK/rec.json" "
a = len(d.get('assumptions') or [])
print('PASS %d assumptions' % a if a else 'FAIL none')"
check "confidence is graded and explained" "$WORK/rec.json" "
c, r = d.get('confidence'), d.get('confidence_reasons') or []
print('PASS %s (%d reasons)' % (c, len(r)) if c else 'FAIL missing')"
check "an imputed charge is labelled, never hidden" "$WORK/rec.json" "
lines = [x for e in d.get('comparison') or []
         for x in e['estimated_cost']['components'] if x.get('is_imputed')]
unlabelled = [x for x in lines if not x.get('imputation_note')]
print('PASS %d imputed, all labelled' % len(lines) if not unlabelled
      else 'FAIL %d imputed without a note' % len(unlabelled))"
check "result is labelled as not financial advice" "$WORK/rec.json" "
print('PASS' if 'not financial advice' in (d.get('disclaimer') or '') else 'FAIL')"

curl -s --max-time 20 -X POST "$BASE/api/recommendations" \
  -H 'Content-Type: application/json' -o "$WORK/badrec.json" -d '{"profile":{}}'
check "incomplete profile is refused, not guessed at" "$WORK/badrec.json" "
code = (d.get('error') or {}).get('code')
print('PASS %s' % code if code == 'PROFILE_INCOMPLETE' else 'FAIL %s' % code)"

# --- Agent ------------------------------------------------------------------
echo
echo "Agent"
curl -s --max-time 240 -X POST "$BASE/api/chat" \
  -H 'Content-Type: application/json' -o "$WORK/chat.json" \
  -d '{"message":"I am an Indian student going to the UK for a two year masters. I will spend about 1100 pounds a month and will not withdraw much cash."}'

check "agent responds" "$WORK/chat.json" "
m = (d.get('message') or '').strip()
print('PASS %d chars' % len(m) if m else 'FAIL empty reply')"
check "agent called real tools" "$WORK/chat.json" "
t = [e['tool_name'] for e in (d.get('tool_events') or [])]
print('PASS %s' % ' -> '.join(t) if t else 'FAIL no tool events')"
check "every tool event is timed" "$WORK/chat.json" "
ev = d.get('tool_events') or []
bad = [e for e in ev if e.get('duration_ms') is None]
print('PASS %d events' % len(ev) if ev and not bad else 'FAIL %d untimed' % len(bad))"
check "profile was extracted" "$WORK/chat.json" "
p = d.get('profile') or {}
print('PASS %s / %s' % (p.get('destination_country'), (p.get('monthly_spend') or {}).get('currency'))
      if p.get('destination_currencies') else 'FAIL nothing extracted')"

SESSION=$(python3 -c "
import json
print(json.load(open('$WORK/chat.json')).get('session_id',''))
" 2>/dev/null)

if [[ -n "$SESSION" ]]; then
  curl -s --max-time 20 "$BASE/api/sessions/$SESSION" -o "$WORK/session.json"
  check "session can be rehydrated" "$WORK/session.json" "
print('PASS %d messages, %d tool events' % (len(d.get('messages') or []), len(d.get('tool_events') or []))
      if d.get('exists') else 'FAIL missing')"
fi

# A real query, so the stream exercises tool events and a result — not just text.
curl -s --max-time 240 -N -X POST "$BASE/api/chat/stream" \
  -H 'Content-Type: application/json' -o "$WORK/stream.txt" 2>/dev/null \
  -d '{"message":"Going to the UK for two years, about 1100 pounds a month, little cash."}'
KINDS=$(python3 -c "
import json
kinds=[]
for line in open('$WORK/stream.txt'):
    if line.startswith('data: '):
        try: kinds.append(json.loads(line[6:])['type'])
        except Exception: pass
print(','.join(dict.fromkeys(kinds)))
" 2>/dev/null)
if [[ -z "$KINDS" ]]; then
  report "streaming endpoint emits events" "FAIL no SSE frames"
elif [[ "$KINDS" != *tool_event* ]]; then
  report "streaming endpoint emits events" "FAIL no tool_event frames: $KINDS"
else
  report "streaming endpoint emits events" "PASS $KINDS"
fi

# --- Product ----------------------------------------------------------------
echo
echo "Product"
if [[ -n "$SLUG" ]]; then
  curl -s --max-time 20 -X POST "$BASE/api/application-click" \
    -H 'Content-Type: application/json' -o "$WORK/click.json" \
    -d "{\"session_id\":\"00000000-0000-0000-0000-000000000001\",\"slug\":\"$SLUG\"}"
  check "application click resolves a URL" "$WORK/click.json" "
u = d.get('application_url')
print('PASS %s' % u[:44] if u else 'FAIL %s' % ((d.get('error') or {}).get('code')))"
fi

curl -s --max-time 20 -X POST "$BASE/api/events" \
  -H 'Content-Type: application/json' -o "$WORK/event.json" \
  -d '{"session_id":"00000000-0000-0000-0000-000000000001","event":"steal_everything"}'
check "unknown analytics event is rejected" "$WORK/event.json" "
code = (d.get('error') or {}).get('code')
print('PASS %s' % code if code == 'UNKNOWN_EVENT' else 'FAIL accepted')"

status "admin surface is locked" "$BASE/admin/cards" 401 UNAUTHORIZED

echo
echo "──────────────────────────────────────────────────────────"
printf '  %d passed, %d failed\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
