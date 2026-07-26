# agent-time-bench — design

## What this measures

LLM agents constantly move date/time values across three representations:

1. the user's words ("last week", "the Friday before Memorial Day"),
2. tool-call arguments (almost always ISO 8601, almost always UTC),
3. tool results back into words for the user ("you paid it on the 3rd", "9pm last night").

Each hop crosses a timezone, a locale convention (week start, date order), and an
ambiguity policy — exactly the operations LLMs are documented to fumble
(Test of Time, arXiv:2406.09170; DateLogicQA, arXiv:2412.13377). This benchmark
measures those hops **in situ**: not "can the model add 7 days" quiz-style, but
*did the agent put the right bounds on the search it just ran for a user, and did
it speak the result back in the user's time*.

The benchmark is treatment-neutral. The primary experiment it was built for is
measuring the lift from giving agents deterministic time tools
([nl2time](https://github.com/AndyFooBlah/nl2time)) plus a skill (prompt
instructions) for using them — but the baseline condition (no time tools) is a
self-contained measurement of agent time competence, and other treatments
(different libraries, different skills, bigger models) drop into the same matrix.

## Anatomy of a scenario

Every scenario is single-turn and fully pinned:

- **context** — the reference instant `now` (with offset), the user's IANA
  timezone, and locale. Nothing about time is left to the harness environment.
- **user utterance** — contains (or requires producing) a natural-language time
  expression.
- **domain tools** — mocked; specs say how time args must be formatted (usually
  "UTC ISO 8601"). Mocks return canned data containing timestamps.
- **expectations** — two graded surfaces:
  - **NL → time**: the time-bearing arguments of the tool call(s) the agent
    makes. Only declared args are graded; everything else (search strings,
    limits) is ignored. Acceptance is a set of admissible intervals with
    documented tolerances (below).
  - **time → NL**: the agent's final text. Graded by per-scenario acceptance
    checks over the rendered time claims (accept/reject regex classes over a
    normalized response), mirroring nl2time's reverse-corpus acceptance-class
    approach. Every scenario's mock data is constructed so the correct answer
    is *checkable from timestamps alone* (e.g. the count of matching rows, the
    civil day of a payment in the user's zone).

A scenario exercises one or both directions; every domain's set of ten exercises
both several times, plus at least one **trap** case where the naive UTC reading
and the correct local reading differ (cross-midnight, month boundary, DST, week
start).

### Tolerances (grading, both conditions)

- Interval bounds: exact half-open `[start, end)` is canonical; an inclusive end
  up to 1s early (`23:59:59`) is accepted, as is `end` given as the last
  millisecond. Mirrors nl2time corpus tolerances.
- Where the utterance is *genuinely* ambiguous under the pinned context, the
  expectation lists every admissible interval; matching any passes. Nothing else
  does — "close" is wrong.
- Numeric answer checks (counts, day-of-month) are exact.

## Domains (10 × 10 scenarios)

| # | Domain | Tool flavor | Characteristic traps |
|---|---|---|---|
| 1 | personal-finance | search transactions, bill history | week start, "last month" boundary, cross-midnight purchase |
| 2 | calendar | availability query, event creation | "next Tuesday", durations, all-day vs timed |
| 3 | email | search by sender/date | "earlier this week", received-at rendering |
| 4 | devops | log/incident queries (UTC-native) | UTC↔local both directions, "last night's deploy", durations |
| 5 | travel | flight search & status | *airport-local* times, multi-zone rendering |
| 6 | ecommerce | order history, delivery ETA | "arrives tomorrow by 8pm", holiday-weekend windows |
| 7 | fitness | workout/sleep queries | sleep sessions spanning midnight, "last Tuesday" |
| 8 | smart-home | sensor event history | "while we were away", most-recent-event rendering |
| 9 | project-mgmt | issues due/updated queries | "end of next week", business days, overdue rendering |
| 10 | media-library | photo search by taken-date | named holidays ("Memorial Day weekend"), "last summer" |

All English, US locales dominant with a few en-GB contexts (week-start contrast),
several context dates placed near DST transitions and month/year boundaries on
purpose. More languages/domains later.

## Conditions & run matrix

A **run** = (model) × (condition) × (skill version) over all 100 scenarios.

- **baseline** — domain tools only; the agent does time math itself.
- **nl2time** — adds two tools backed by the nl2time JS library via a local
  bridge (`harness/tools/nl2time_bridge`):
  - `resolve_timephrase(phrase) → {start_utc, end_utc, grain, alternatives[]}`
  - `describe_time(timestamps_utc[]) → phrases[]` (casual + neutral forms)
  Context (now/tz/locale) is injected by the harness, not trusted to the model.
- **skills** — versioned markdown system-prompt fragments (`skills/`) telling
  the agent when/how to use the time tools (and, in baseline, nothing beyond the
  generic agent instructions, so the comparison isolates tools+skill).

The agent harness is Google **ADK** (Python), single `LlmAgent`, function tools,
in-memory sessions; model strings are pluggable (Gemini native now; other
vendors via ADK's LiteLLM wrapper later — nothing in scenarios or grading is
Gemini-specific).

## Scoring & reporting

Per scenario: `nl2time_args` (0/1 per graded tool-call expectation),
`nl2nl_response` (0/1 per response check), plus diagnostics (which tolerance
fired, raw args, full response). Per run: direction-level and domain-level
accuracy; the headline chart is baseline vs. treatment accuracy per direction
per model. All run artifacts are JSONL under `results/` (gitignored raw, with
committed summaries).

Framework: thin custom runner (see `docs/framework-choice.md` for the
evaluation of EvalBench / ADK-native eval / Inspect AI that led here).

## Correctness discipline for expectations

Golden bounds are computed twice: by hand at authoring time (documented in a
`rationale` field) and mechanically via nl2time's resolver; disagreement blocks
the scenario until resolved. nl2time is *also* the treatment, so every
mechanically-computed expectation must carry a human-verified rationale — the
benchmark must never be circular ("correct = whatever nl2time says"). Scenario
reviews happen in PRs with the rationale visible.
