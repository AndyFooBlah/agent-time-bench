# Authoring scenarios — rules learned the hard way

Read [scenarios.md](scenarios.md) first; [`scenarios/personal-finance.json`](../scenarios/personal-finance.json)
is the exemplar. These rules exist because the first hand-authored batch
contained two wrong goldens — both caught by the checks below. Follow them
mechanically.

## Never do date math in your head

Every golden bound, every mock timestamp's local reading, every weekday claim
in a `rationale` must be computed by running code:

```bash
python3 - <<'EOF'
from datetime import datetime
from zoneinfo import ZoneInfo
utc = datetime.fromisoformat('2026-07-01T02:05:00+00:00')
print(utc.astimezone(ZoneInfo('America/New_York')))   # → weekday, local day, offset
EOF
```

and cross-checked with the bridge where nl2time can parse the phrase:

```bash
echo '{"op":"resolve","phrase":"last week","context":{"now":"2026-07-22T08:15:00-04:00","timeZone":"America/New_York","locale":"en-US"}}' | node bridge/bridge.mjs
```

## The trap that got us: "last week" anchored on a Sunday

With Monday-start weeks, on a Sunday the *current* week began 6 days ago —
"last week" is the week before that. Convention bugs like this are exactly what
the benchmark measures, so the corpus must be immune to them:

- **Bare week phrases → midweek `now`** (Tue–Thu). Then Sunday-start and
  Monday-start readings overlap on the interior.
- Both conventions go in `admissible` (as complete tuples); **no mock rows on
  the disputed edge days**, so the graded count is identical under every
  admissible tuple. `verify_goldens.py` fails the file otherwise.
- Convention-*testing* scenarios must pin the convention in words ("Monday
  through Friday last week") or via an unambiguous phrase.

## Mandatory mechanics

- `context.now` must carry the real offset of `timeZone` at that instant
  (verified mechanically — e.g. New York in July is `-04:00`).
- `verifyPhrase` on every tool-call expectation whose time phrase nl2time can
  parse (use the user's exact wording). If the bridge disagrees with your
  golden: **stop and re-derive by hand**. If your golden is right and nl2time
  is wrong, add `disagreementNote` AND report the disagreement in your summary
  — do not silently paper over it in either direction.
- Every timestamp referenced by a `civilDay`/`clockTime`/`weekday` check must
  literally appear in the scenario's mock data (verified).
- `rejectUtcDay`/`rejectUtcClock` only when the UTC and local renderings
  actually differ (verified).
- Static-mock tools: if the model could plausibly answer the question by
  calling a static tool, that tool MUST have a per-scenario mock consistent
  with the story (unmocked static tools return "no data available", which is
  wrong if data should exist). Filter-rows tools without rows return empty —
  fine when that's the truth.
- Rationales carry the full derivation: weekday of `now`, offset, local
  readings of the boundary-adjacent rows, and why each decoy row is excluded.

## Scenario mix per domain (10 scenarios)

- ≥6 grading tool-call time args (`nl2time` direction), ≥5 grading response
  rendering (`time2nl`; overlap is normal), of which **≥2 are pure time→NL**
  (tool with no time params, static mock).
- ≥3 real UTC-vs-local traps: a mock row whose UTC day differs from its local
  day near a graded boundary, a rendering check with `rejectUtcDay`, or a
  non-integer-hour offset zone (India `+05:30`, Newfoundland, Nepal).
- ≥1 non-US context (offset ≠ multiples of whole hours from the domain's home
  zone, or a different week convention, or cross-zone rendering).
- Vary `now` across scenarios (different weekdays, at least one near a month
  boundary). Keep everything in 2026 (June–August unless the domain needs
  otherwise; DST-transition dates welcome: US spring-forward was Mar 8 2026,
  fall-back Nov 1 2026; Europe: Mar 29 / Oct 25 2026).
- Graded answers must be checkable from timestamps alone: small counts (2–5),
  a civil day, a wall time, a weekday, yes/no. Never money sums or prose
  quality.
- Phrase variety across the corpus — don't reuse personal-finance's phrases;
  pull from: this weekend, N days ago, the week of the 6th, early next month,
  the morning of the 14th, Friday before last, Q2, mid-July, the past 48
  hours, tonight, end of the month…
- Keep 1–2 scenarios per domain trap-free (honest baseline; not everything
  should be adversarial).

## Tool design per domain

2–4 tools. At least one filter-rows search tool whose param descriptions state
the contract explicitly ("UTC ISO 8601, e.g. 2026-07-01T04:00:00Z; start
inclusive, end exclusive"), and at least one no-time-param static tool
returning timestamp-bearing data for pure time→NL scenarios. Param names may
vary by domain flavor (`start_time`/`end_time`, `from_utc`/`to_utc`) — the
expectation's `argKinds`/`graded` and the mock's `startParam`/`endParam` bind
them.

## Verify before you finish

```bash
python3 -m json.tool scenarios/<domain>.json > /dev/null
uv run --project harness python scripts/verify_goldens.py <domain>
uv run --project harness atb validate
```

All three must pass, and you must eyeball the printed in-range row selections
for every merchant/name-scoped count.
