# Blind golden audit — 2026-07-26

## Method

Three independent auditors (A, B, C) re-derived all **78 graded tool-call
expectations** from goldens-stripped scenario files: each auditor saw the
scenario `context`, `user` text, tool specs, and mock rows, but **no**
`admissible` tuples, no `rationale`, and no access to the nl2time bridge —
derivations were done with raw `zoneinfo` arithmetic only. Each auditor
produced, per scenario, the full set of admissible arg tuples they considered
defensible.

## Results

- **57/78 expectations: exact tuple-set agreement** between all auditors and
  the shipped goldens.
- **21 expectations flagged** (some auditor's set differed from the goldens).
  Adjudication sorted every flag into one of four buckets:

### (a) Goldens broader but answer-invariant — kept

For a number of flags the shipped goldens admitted more readings than an
auditor enumerated (or vice versa), but every disputed tuple selects the same
mock rows, so no graded answer could change. These goldens were kept as-is.

### (b) Two genuine golden gaps — fixed

1. **pm-01** (project-mgmt): the deadline family "by the end of next week"
   was missing the **work-week (Fri-EOD)** reading. The end family is now
   Fri-EOD / Sat-EOD / Sun-EOD: Fri Jul 31 EOD = `2026-08-01T04:00:00Z`,
   Sat Aug 1 EOD = `2026-08-02T04:00:00Z` (Sunday-start week), Sun Aug 2 EOD
   = `2026-08-03T04:00:00Z` (Monday-start week), each crossed with the two
   admissible starts (now / start-of-today) — 6 tuples. PM-322 (due Fri Jul 31
   10:00pm EDT = `2026-08-01T02:00:00Z`) is inside all of them, so the graded
   count (3) is invariant.
2. **fit-10** (fitness): the "last night" sleep-attribution family was
   missing the **start-of-today → now** reading (Wed 00:00 AEST .. now
   8:05am AEST). Now admitted via the window conversion below: that window
   contains the core and fits the envelope.

### (c) Systemic finding: fuzzy-window families → core/envelope grading

The audit demonstrated that colloquial windows ("Tuesday night", "this
morning", "yesterday evening", "overnight", "earlier this week") form
*families* of defensible bounds that tuple enumeration cannot cover — every
auditor produced a defensible set that differed from every other. These
expectations were converted from `admissible` tuple lists to
`admissibleWindow` `{core, envelope}` grading (pass iff
core ⊆ [start, end) ⊆ envelope, with `verify_goldens.py` enforcing
`rows(core) == rows(envelope)` — answer invariance):

| Scenario | File | Phrase |
|---|---|---|
| fit-01 | scenarios/fitness.json | "Tuesday night" (sleep wake-attribution) |
| fit-03 | scenarios/fitness.json | "this morning" |
| fit-10 | scenarios/fitness.json | "last night" (sleep wake-attribution) |
| med-06 | scenarios/media-library.json | "the morning of July 4th" |
| cal-02 | scenarios/calendar.json | "tomorrow morning" |
| trv-10 | scenarios/travel.json | "the morning of the 14th" |
| home-03 | scenarios/smart-home.json | "yesterday evening" |
| home-05 | scenarios/smart-home.json | "overnight" |
| home-06 | scenarios/smart-home.json | "last night" (house-zone pinned) |
| eml-01 | scenarios/email.json | "earlier this week" |

### (d) Policy rulings — codified in docs/scenarios.md ("Reading policies")

- **Weekend = the locale's weekend civil days** (CLDR; Sat 00:00 → Mon 00:00
  local for all current locales). Friday-evening-inclusive readings are NOT
  admissible: colloquial "weekend trips" start Friday night, but "what
  happened over the weekend" denotes the weekend days. The Friday-evening
  rows in **dev-07, eco-02, pm-09, trv-08, home-02** are traps outside every
  admissible reading.
- **Duration-anchored sliding windows end at now** ("past 48 hours" =
  exact arithmetic from now; calendar rounding inadmissible).
- **Night starts no earlier than 20:00 local** (18:00–20:00 is "evening");
  sleep-attribution tools extend the family to wake-covering windows per
  their stated contract. This resolves the **home-06** boundary row: the
  19:05 PDT door open (`2026-07-16T02:05:00Z`) is outside every admissible
  reading of "last night" at the house.
- **Morning** envelope is [00:00, 12:00) local (end may extend to now when
  now is barely past noon); **evening** is [17:00, 24:00) local;
  **overnight** is [20:00 previous evening, max(07:00, now)] local;
  **"earlier this week"** spans [locale-or-ISO week start, end-of-week]
  with rows never postdating now.

## Scenarios changed by this audit

- Window conversion (bucket c): fit-01, fit-03, fit-10, med-06, cal-02,
  trv-10, home-03, home-05, home-06, eml-01.
- Tuple additions (bucket b): pm-01 (Fri-EOD end × two starts).
- No mock rows, response checks, or contexts were altered; rationales were
  rewritten for the converted scenarios to carry the core/envelope
  derivations.

Auditor derivations are preserved outside the repo (blind-audit working
files); the adjudicated policies above are the normative record.
