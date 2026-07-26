# Run 1 — gemini-3.5-flash-lite, baseline vs nl2time (2026-07-26)

Full corpus (10 domains × 10 scenarios), single-turn ADK agents via Vertex
(`GOOGLE_CLOUD_LOCATION=global`), skill `nl2time-v1`, 200 scenario-runs, 0 errors.
Raw rows: `run1-flash-lite.jsonl` (+ `-regraded.jsonl` after the grader-fairness
pass below; raw JSONL is gitignored, this summary is the committed record).

## Headline

| direction | baseline | nl2time tools + skill | lift |
|---|---|---|---|
| NL → time (tool-call bounds correct) | **21/78 = 26.9%** | **69/78 = 88.5%** | +61.6pt |
| time → NL (response renders timestamps correctly) | **52/100 = 52.0%** | **81/100 = 81.0%** | +29.0pt |

## Per-domain, NL → time (passed/graded)

| domain | baseline | nl2time |
|---|---|---|
| calendar | 7/8 | 7/8 |
| devops | 2/8 | 7/8 |
| ecommerce | 0/7 | 6/7 |
| email | 0/8 | 7/8 |
| fitness | 4/8 | 6/8 |
| media-library | 2/8 | 8/8 |
| personal-finance | 2/8 | 7/8 |
| project-mgmt | 0/8 | 7/8 |
| smart-home | 3/8 | 7/8 |
| travel | 1/7 | 7/7 |

## Failure anatomy (audited case by case)

**Baseline (57 arg failures)** — dominant modes: UTC-midnight bounds instead of
local-midnight (the classic), wrong week identification, half-hour-offset zones
(Kolkata, St. John's) handled as whole hours, month/quarter boundaries at 00:00Z.

**Treatment (9 arg failures)** — **zero model errors**: every one is the model
faithfully passing through a documented nl2time wrong reading (filed as
nl2time#17–#24: between-inclusive, since/until, midnight-truncated night
windows, dropped qualifiers) or a deliberate domain-semantics case (sleep
windows keyed to wake time; cross-zone "at the house"). Fixing the library
mechanically raises this score — the benchmark now regression-tests nl2time.

**Treatment response failures (19)** — 7 downstream of the arg bugs above; the
rest genuine model behavior worth writing up:
- *UTC re-filtering*: model receives correctly-filtered rows, then eyeballs
  UTC timestamps and drops valid rows in its prose ("2 orders in Q2 — note: the
  June 30 one was excluded"). The tool was right; the model overruled it.
- *Cross-zone rendering*: flight times labeled "departure airport time" that
  are actually the user's home-zone rendering; Paris photo rendered in ET.
- Arithmetic slips (airport arrival 4h instead of 2h before departure).

## Grader-fairness pass (regraded, no reruns)

Post-run audit added: deictic day acceptance ("yesterday at 5:10 PM", "last
Saturday" now count as identifying the day, anchored to the scenario's pinned
now, with symmetric conservative rejects for the wrong UTC day), "once/twice"
wordforms, `itemRegex` enumeration counting (a bulleted list of the right N
items passes without a stated total), and two over-broad `\bno\b` scenario
rejects narrowed. `atb regrade` re-scores recorded transcripts under the
current graders at zero model cost. Both conditions were regraded identically;
the fixes raised baseline 45→52 and treatment 61→81 on time→NL (the treatment
gained more because `describe_time` speaks deictically — exactly the phrasing
the old grader under-credited).

## Next

1. Skill iteration (issue #1): the residual model failure modes are prompt-able
   — "never re-filter tool results by timestamp", "render in the zone the data
   is about, not yours". 2. nl2time fixes #17–#24, then re-run. 3. Multi-model
   matrix (issue #2).
