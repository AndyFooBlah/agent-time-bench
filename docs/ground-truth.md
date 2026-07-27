# Ground truth: what makes a golden correct, and how we prove it

A benchmark's conclusions are only as good as its goldens. This document
states what "correct" means for a time expression, layer by layer, and the
chain of independent checks each golden must survive. Everything here runs in
CI; nothing relies on trusting the author.

## The three layers of "correct"

**1. The physical/civil layer — objective.** Instant arithmetic, timezone
conversion, DST transitions, weekday-of-date. Ground truth is the **IANA tz
database** (with ISO-8601 for representation). There is no judgment here: for
a given instant and zone, the local wall time, calendar day, offset, and
weekday are facts. The benchmark touches tzdb through two independent
implementations — Python's `zoneinfo` (all verifiers and audits) and JS
`Temporal` (inside nl2time) — so a systematic error in one cannot silently
define the goldens.

**2. The convention layer — standardized.** Which day a week starts on, how
dates are ordered, what a quarter is. Ground truth is **Unicode CLDR**
(week data per territory: en-US Sunday, en-GB Monday) plus ordinary calendar
definitions (Q2 = Apr–Jun). These are lookups, not opinions.

**3. The semantics layer — conversational, policy-governed.** What "last
week", "between July 4th and July 10th", or "overnight" *denote* has no
single authority. The benchmark's policy, applied uniformly:

- **Admissible sets, not single answers.** Every defensible reading under
  layers 1–2 is enumerated as a complete argument tuple; matching any passes;
  anything else fails. "Close" is wrong.
- **Answer-invariance by construction.** Where readings are genuinely
  contested (bare "last week": Sunday- vs Monday-start), scenarios are built
  so every admissible reading selects the *same rows and the same answer* —
  midweek anchors, no data on disputed edge days. A verifier enforces this
  mechanically: admissible tuples selecting different row counts fail the
  build. The contested choice therefore cannot decide any scenario's outcome.
- **Documented stances.** Where the benchmark takes a position (inclusive
  "between DATE and DATE"; deadlines "by X" = [now, end of X)), the stance is
  written down (docs/scenarios.md, per-scenario rationale) and applied
  symmetrically to both conditions. A grader cannot quietly prefer either
  condition: it sees only tool arguments and text.

## The verification chain (every golden, every commit)

1. **Falsifiable rationale** (authoring): each scenario carries a prose
   derivation — weekday of `now`, the offset in effect, the local reading of
   every boundary-adjacent mock row, why each decoy is excluded. Reviewable
   and checkable by hand.
2. **Mechanical verifier** (`scripts/verify_goldens.py`, zoneinfo-based,
   independent of nl2time): `now`'s stated offset must match the zone at that
   instant; admissible tuples must be well-formed and *answer-invariant*
   (identical row selections); every instant referenced by a rendering check
   must exist in the mock data; every declared trap must be real (UTC/local
   actually differ).
3. **Library cross-check** (`verifyPhrase`): nl2time independently resolves
   the scenario's phrase under its context. Agreement corroborates;
   disagreement **fails the build** unless explicitly adjudicated with a
   written `disagreementNote` — and every such note corresponds to a filed,
   public nl2time issue or a documented domain-semantics extension. The
   treatment library never generates goldens; it only corroborates them, and
   its disagreements are evidence (8 library bugs were filed this way before
   any model ran). Circularity is controlled by direction: goldens are
   derived from layers 1–3 policy by hand, then checked against the library —
   never the reverse.
4. **Blind re-derivation audit**: independent auditors receive
   goldens-stripped scenarios (context, utterance, tool contracts, data — no
   expectations, no rationales, no access to the corpus or the library) and
   re-derive the admissible tuples with raw `zoneinfo` arithmetic.
   `scripts/blind_audit.py compare` diffs their derivations against the
   goldens as instants; every mismatch is adjudicated in writing (golden
   fixed, or the divergent reading rejected with cause). Audit records live
   in `docs/audits/`.
5. **CI**: 1–3 run on every push; the audit re-runs when the corpus changes
   materially.

## External anchors

The treatment library is itself pinned by third-party human-annotated
conformance data (Microsoft Recognizers-Text specs, ~2,700 imported cases,
MIT, plus hand-authored sets) — an annotation lineage with no stake in this
benchmark. So when `verifyPhrase` corroborates a golden, that corroboration
transitively reflects an independent annotation tradition, not this repo's
own opinions.

## Honest limitations (for the writeup)

- Layer 3 is policy, not physics. A different defensible policy (exclusive
  "between", strict-ISO weeks everywhere) would grade some scenarios
  differently. The mitigations are admissible sets, answer-invariance, and
  publishing the policy — not a claim of unique truth.
- Free-text grading is approximate by nature. Checks anchor on facts (a
  count, a civil day, a wall time), accept generously (explicit, deictic, and
  weekday forms all count), and reject only unambiguous wrong renderings; the
  planned LLM-judge secondary metric (issue #3) will measure how often the
  deterministic checks and a rubric judge disagree.
- Mocked tools are simplifications of real APIs; the `filter-rows` mock's
  half-open `[start, end)` contract is stated in every tool description, so
  agents are graded against the contract they were shown.
