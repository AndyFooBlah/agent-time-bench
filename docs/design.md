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

A scenario exercises one or both directions (`directions: ["nl2time", "time2nl"]`
in the scenario); every domain's set of ten exercises both several times, plus
at least one **trap** case where the naive UTC reading and the correct local
reading differ (cross-midnight, month boundary, non-whole-hour offset, week
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

Actual coverage of the current corpus (computed from `scenarios/*.json`): all
100 scenarios are English-language utterances; locales are 83% `en-US`, with
`en-IN` (8), `en-AU` (3), `en-DE` (2), `en-NZ`, `de-DE`, `en-GB`, `en-CA` (1
each) — the non-US locales supply the Monday-start week convention. Zones: 10,
led by `America/New_York` (56) and `America/Chicago` (15); the non-whole-hour
offsets are `Asia/Kolkata` (9, +05:30) and `America/St_Johns` (1, −02:30 in
summer). Every `context.now` falls between 2026-06-01 and 2026-08-20, i.e.
mid-summer in every zone: **no scenario's `now` is within a week of a DST
transition**, so DST-day behaviour (23/25-hour days, non-existent wall times)
is not measured by this corpus. A dedicated DST/edge-zone stress set and
non-English utterances are tracked in issue #4.

## Conditions & run matrix

A **run** = (model) × (condition) × (skill version) over all 100 scenarios.

- **baseline** — domain tools only; the agent does time math itself.
- **nl2time** — adds two tools (`harness/src/atb/nl2time_tools.py`) backed by
  the nl2time JS library through a stdin/stdout JSON bridge (`bridge/bridge.mjs`,
  one Node process per call):
  - `resolve_timephrase(phrase, direction?: "past"|"future", time_zone?)
    → {ok, interpreted_as, start, end, grain, alternatives[]}` — `start`/`end`
    are UTC ISO 8601 (half-open); `alternatives` lists other admissible readings.
  - `describe_time(timestamps_utc[], time_zone?) → {ok, phrases[{instant, casual, neutral}]}`
  Context (now / timeZone / locale) is injected by the harness, not trusted to
  the model; the optional `time_zone` lets the agent resolve or render in a
  different place's zone (an airport, the house) than the user's.
- **skills** — versioned markdown system-prompt fragments (`skills/`) telling
  the agent when/how to use the time tools (and, in baseline, nothing beyond the
  generic agent instructions, so the comparison isolates tools+skill).

The agent harness is Google **ADK** (Python), single `LlmAgent`, function tools,
in-memory sessions; model strings are pluggable (Gemini natively;
`litellm:<provider>/<model>` selects ADK's LiteLLM wrapper for other vendors —
nothing in scenarios or grading is Gemini-specific).

## Scoring & reporting

Per scenario row: `nl2time_pass` (true iff every graded tool-call expectation
matched an admissible tuple; `null` if the scenario does not grade that
direction) and `time2nl_pass` (true iff every response check passed), plus
diagnostics (`tool_results`, `check_results`: which tuple/tolerance matched,
raw args, full response). Per run (`atb report`): direction-level and
domain-level accuracy; `atb compare` pairs conditions by scenario to list
fixes and regressions. The headline chart is baseline vs. treatment accuracy
per direction per model. Run artifacts are JSONL under `results/`; the
published sweep rows are committed, everything else is local scratch (see
`results/README.md`).

Framework: thin custom runner (see `docs/framework-choice.md` for the
evaluation of EvalBench / ADK-native eval / Inspect AI that led here).

## Correctness discipline for expectations

Golden bounds are computed twice: by hand at authoring time (documented in a
`rationale` field) and mechanically via nl2time's resolver; disagreement blocks
the scenario until resolved. nl2time is *also* the treatment, so every
mechanically-computed expectation must carry a human-verified rationale — the
benchmark must never be circular ("correct = whatever nl2time says"). Scenario
reviews happen in PRs with the rationale visible.
