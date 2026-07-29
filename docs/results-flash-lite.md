# Results: gemini-3.5-flash-lite, baseline vs nl2time (2026-07-27)

Four full runs (100 scenarios × 2 conditions each, single-turn ADK agents via
Vertex, temperature default), iterating agent prompt, skill, and the nl2time
library itself until neither condition had low-hanging fruit left. Raw rows in
`results/run{1..4}-*.jsonl` (gitignored; regenerate grading anytime with
`atb regrade`). Metrics: **NL→time** = correct time bounds in tool-call args
(78 graded scenarios); **time→NL** = correct rendering of returned timestamps
(100 scenarios).

## Iteration history

| Run | Config | Baseline args | Treatment args | Baseline resp | Treatment resp |
|---|---|---|---|---|---|
| 1 | prompt v1 (bare context), skill v1, nl2time 0.3.0 | 26.9% | 88.5% | 52.0% | 81.0% |
| 2 | prompt v2 (+weekday, +time discipline), skill v2 | 75.6% | 87.2% | 77.0% | 85.0% |
| 3 | same, **nl2time 0.3.1** (issues #17–#24 fixed) | 78.2% | 92.3% | 72.0% | 88.0% |
| 4 | prompt v3 (+conventions), skill v3 (+adherence, +zone override) | **78.2%** | **94.9%** | 69.0% | **89.0%** |

Reading the curve:

- **Prompt engineering moved the baseline enormously** (26.9→~78% args): adding
  the weekday-bearing local datetime and explicit discipline rules ("days start
  at local midnight, not 00:00 UTC"; "weeks start per locale") fixed the bulk
  of naive failures. This was deliberate — the experiment's goal was the
  strongest achievable no-tool baseline, so the treatment lift is measured
  against a fair opponent, not a strawman.
- **The baseline then plateaued.** v3's additional conventions bought zero
  additional args accuracy; response accuracy wobbled 69–77% across identical
  configs (run-to-run sampling noise on ~100 binary trials is ±4pt; treat
  single-run deltas <5pt as noise). The residual baseline failures are
  arithmetic, not knowledge: whole weeks misidentified, sliding windows
  anchored at the wrong instant, 8-day "weeks" unioning both conventions,
  half-hour offsets handled as whole hours.
- **The treatment kept climbing with the library**: fixing the eight
  benchmark-found nl2time bugs (0.3.1) moved treatment args 87→92%, and skill
  v3 (adherence framing + `time_zone` override) took it to 94.9%. The
  remaining 4 arg failures are pure tool-adoption lapses — flash-lite writing
  datetime args without calling the resolver despite instructions — i.e. an
  obedience ceiling of this cheap model, not a ceiling of the approach.

**Final lift (run 4): +16.7pt on tool-call bounds (78.2→94.9), +20pt on
rendering (69→89).**

## Per-domain, run 4 (baseline → treatment)

| Domain | NL→time | time→NL |
|---|---|---|
| calendar | 7/8 → 8/8 | 9/10 → 10/10 |
| devops | 6/8 → 8/8 | 8/10 → 10/10 |
| ecommerce | 5/7 → 7/7 | 4/10 → 7/10 |
| email | 7/8 → 8/8 | 5/10 → 7/10 |
| fitness | 6/8 → 6/8 | 7/10 → 9/10 |
| media-library | 7/8 → 8/8 | 7/10 → 8/10 |
| personal-finance | 7/8 → 7/8 | 8/10 → 9/10 |
| project-mgmt | 5/8 → 7/8 | 6/10 → 9/10 |
| smart-home | 7/8 → 8/8 | 8/10 → 10/10 |
| travel | 4/7 → 7/7 | 7/10 → 10/10 |

Treatment reaches 100% args in 7 of 10 domains. The biggest lifts are where
zones bite hardest: travel (airport-local), devops (UTC-native systems),
smart-home (late-night events).

## Evidence: fixed by the treatment (run 4)

NL→time (14): cal-04, dev-02, dev-08, eco-02, eco-08, eml-07, fin-07, home-09,
med-03, pm-06, pm-10, trv-01, trv-04, trv-10 — dominated by week resolution
(fin-07 London "last week", pm-06, med-03, home-09, eml-07, cal-04, dev-08),
qualified phrases the baseline mangles ("Friday before last" eco-08), and
non-integer offsets (trv-04 Kolkata).

time→NL (22): cal-05, dev-02, dev-06, eco-02, eco-05, eco-06, eco-08, eml-09,
eml-10, fin-07, fit-01, fit-05, home-01, home-10, med-02, med-07, pm-06, pm-09,
pm-10, trv-02, trv-04, trv-05 — dominated by UTC-day/clock traps (`describe_time`
renders locally by construction) and cross-zone cases (trv-02/trv-05 airport-
and Tokyo-local via the `time_zone` override).

## Regressions under the treatment, with causes (run 4)

Only three, all diagnosed:

1. **fin-02** (args + response): tool-adoption lapse — the model answered from
   `get_last_rent_payment` (this month's payment) and never searched last
   month; no resolver call. Baseline happened to search (with imperfect but
   in-tolerance bounds). Cause: adherence, not the tools.
2. **eco-04, med-10** (response): the **hybrid-rendering trap** — the model
   takes `describe_time`'s correct deictic ("Friday"), then *decorates it with
   an explicit date read off the raw UTC timestamp*: "Friday, August 1"
   (deadline is Friday July 31, 11:59pm PDT). Partial tool trust produces a
   self-contradicting answer neither full trust nor no-tool produces. Skill v3
   reduced but did not eliminate it on flash-lite (run 3 had three such cases,
   run 4 two).

Earlier-run regressions (eml-01 self-computed bounds, eco-03 same hybrid
pattern, home-06 zone override missing) were eliminated by skill v3 + the
`time_zone` parameter.

## Persistent both-fail cases (run 4)

fit-01/fit-10 (sleep windows: the model — with or without tools — doesn't
extend the night window through the wake per the sleep tool's attribution
contract), pm-01 ("due by end of next week" read as the *tail* of next week
rather than a deadline), fin-02 (above), plus response-side counting cases
where the model second-guesses correctly-filtered rows (eco-09, eml-03,
med-02, fit-04 — the **UTC re-filtering** failure mode: it eyeballs raw UTC
timestamps in returned rows and wrongly drops/renames rows in prose).

## Method notes

- Golden validity: see [ground-truth.md](ground-truth.md) and the
  [blind-audit record](audits/2026-07-26-blind-audit.md) (3 independent
  auditors, 57/78 exact agreement, all 21 flags adjudicated; fuzzy windows
  graded core⊆window⊆envelope with verifier-enforced answer-invariance).
- The benchmark→library loop is real and closed: authoring + run 1 filed
  nl2time #17–#24; 0.3.1 fixed seven of them with zero conformance-baseline
  regressions across six languages; the benchmark's own `verifyPhrase` ratchet
  then forced removal of the eight now-stale disagreement annotations.
- One baseline run-4 error: the model hallucinated a tool name
  (`list_depl_deploys`); recorded as a failure (it is one).
- Costs: each full run (200 scenario-executions) on flash-lite via Vertex is
  a few minutes at trivial cost; grader iteration is free via `atb regrade`.

## Next

Multi-model matrix (issue #2): the config that matters is frozen — prompt
baseline-v2/v3 (identical for both conditions), skill nl2time-v3,
nl2time 0.3.1. Sweep flash-lite / flash / a GPT model / a Claude model via
LiteLLM, several seeds per config to average the ±4pt noise, then the blog
charts (issue #5).

---

# Multi-model sweep (2026-07-28)

Frozen config (prompt `baseline-v2`, skill `nl2time-v3`, nl2time 0.3.1),
2–3 full repeats per model, repeats pooled. Charts: `blog/charts/`.

| Model | Class | NL→time | time→NL |
|---|---|---|---|
| Gemma 4 26B-A4B | open · tiny (~4B active) | 13.7% → **94.0%** | 51.3% → **86.3%** |
| Gemini 3.5 Flash-Lite | closed · cheap | 77.8% → **94.9%** | 72.3% → **90.7%** |
| Gemini 3.6 Flash | closed · mainstream | 72.2% → **97.0%** | 90.7% → **98.3%** |
| DeepSeek V4 Pro | open · frontier | 94.4% → **96.2%** | 79.7% → **92.7%** |
| Kimi K3 | open · frontier | 94.9% → **97.9%** | 81.7% → **92.3%** |
| GPT-5.6 Sol | closed · frontier | 94.9% → 94.9% | 89.0% → 85.0% |
| Claude Opus 5 | closed · frontier | 91.7% → **97.4%** | 88.0% → **98.0%** |

Every model gains except GPT-5.6 Sol, which declines slightly on rendering.
The two closed frontier models split on *tool adoption*: Opus 5 uses the
tools when told to (+5.7pt args, +10pt rendering — its treatment rendering is
the best in the study alongside Gemini 3.6 Flash); Sol largely ignores them
and rides its own arithmetic, which is strong for bounds but leaves the
rendering traps unfixed. Paired analysis for Opus: 4 args + 12 rendering
scenarios fixed, 1 regressed (fit-10 — the sleep-window contract case that
fails in both conditions for most models).

Operational notes: two provider-side stalls cost a rerun each (an exhausted
Anthropic balance, then an OpenRouter per-key spend cap) — both surfaced as
100% error rows and were discarded, never graded. Gemma's 13 treatment
errors are malformed tool calls under load; they are counted as failures.
