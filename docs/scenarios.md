# Scenario format & grading semantics

One JSON file per domain: `scenarios/<domain>.json`, validating against
[`schema/scenario.schema.json`](../schema/scenario.schema.json).

```jsonc
{
  "domain": "personal-finance",
  "description": "Consumer banking assistant",
  "tools": [ /* ToolSpec[] — shared by all scenarios in the domain */ ],
  "scenarios": [ /* Scenario[] */ ]
}
```

## ToolSpec

Declares what the model sees (name, description, params — descriptions carry the
format contract, e.g. "UTC ISO 8601, exclusive") and how the mock behaves.

```jsonc
{
  "name": "search_transactions",
  "description": "Search the user's transactions. Both bounds are required, UTC ISO 8601; start inclusive, end exclusive.",
  "params": [
    {"name": "query", "type": "string", "description": "Free-text merchant filter", "required": false},
    {"name": "start_utc", "type": "string", "description": "Start bound, UTC ISO 8601 (e.g. 2026-07-01T00:00:00Z), inclusive", "required": true},
    {"name": "end_utc", "type": "string", "description": "End bound, UTC ISO 8601, exclusive", "required": true}
  ],
  "mock": {
    "kind": "filter-rows",          // or "static"
    "rowsKey": "transactions",      // response = {"transactions": [...matching rows...]}
    "timestampField": "timestamp_utc",
    "startParam": "start_utc",      // rows filtered by [start, end) against these args
    "endParam": "end_utc"
  }
}
```

**Mock behavior is part of the benchmark's realism.** `filter-rows` mocks apply
the agent's *actual* bounds to the scenario's canned rows — wrong bounds produce
wrong data, which propagates into a wrong final answer, exactly like production.
Unparseable datetime args return a tool error (real APIs 400). `static` mocks
return `response` verbatim; scenarios that isolate the time→NL direction use
tools with **no time parameters** (e.g. `get_last_rent_payment()`) so response
grading is not confounded by argument mistakes.

Per-scenario `rows`/`response` live on the scenario (under `mocks`), keyed by
tool name; the ToolSpec holds only the mechanism.

## Scenario

```jsonc
{
  "id": "fin-01",
  "title": "starbucks-last-week",
  "context": {
    "now": "2026-07-26T08:15:00-04:00",   // offset REQUIRED — self-contained
    "timeZone": "America/New_York",
    "locale": "en-US"
  },
  "user": "How many times did I buy Starbucks last week?",
  "mocks": {
    "search_transactions": { "rows": [ /* superset spanning the boundary */ ] }
  },
  "expect": { "toolCalls": [ /* ToolCallExpectation[] */ ],
              "response":  { "checks": [ /* ResponseCheck[] */ ] } },
  "directions": ["nl2time", "time2nl"],   // which metrics this scenario feeds
  "rationale": "en-US ⇒ Sunday week start. Last week = Sun Jul 19 00:00 ET … Sun Jul 26 00:00 ET = [2026-07-19T04:00:00Z, 2026-07-26T04:00:00Z). 4 of the 6 canned rows fall inside."
}
```

`context` is injected into the system prompt identically in every condition
("Current date & time: … / User timezone: … / Locale: …"). `rationale` is
mandatory: the human-verified derivation of every golden value (see
[design.md](design.md) — goldens are also cross-checked mechanically, and the
two must agree).

## ToolCallExpectation (NL → time grading)

```jsonc
{
  "tool": "search_transactions",
  "graded": ["start_utc", "end_utc"],           // ONLY these args are graded
  "argKinds": {"start_utc": "instant-start", "end_utc": "instant-end"},
  "admissible": [                                // list of admissible arg TUPLES
    {"start_utc": "2026-07-19T04:00:00Z", "end_utc": "2026-07-26T04:00:00Z"}
  ]
}
```

- A scenario passes an expectation if **any** captured call to that tool matches
  **one** admissible tuple on **all** graded args. Tuples keep coupled
  alternatives coupled — a Sunday-start `start_utc` cannot pair with a
  Monday-start `end_utc`.
- `argKinds`:
  - `instant-start` / `instant` — parsed and compared as instants
    (`2026-07-19T04:00:00Z` ≡ `2026-07-19T00:00:00-04:00`); exact.
  - `instant-end` — same, plus **inclusive-end tolerance**: a value 1s or 1ms
    below the golden end (`23:59:59`-style) passes. Mirrors nl2time corpus
    tolerances.
  - `date` — plain `YYYY-MM-DD` string equality.
  - `string` — case-insensitive string equality.
- Genuine ambiguity ⇒ multiple tuples; anything else fails. "Close" is wrong.
- Ungraded args are ignored entirely.

## ResponseCheck (time → NL grading)

Checks run over the agent's final text, normalized (lowercased, whitespace
collapsed, markdown stripped). All must pass for the scenario's response point;
per-check results are recorded.

```jsonc
{"kind": "count",     "expected": 4, "unit": "times?|purchases?"}
{"kind": "civilDay",  "instant": "2026-07-04T01:30:00Z", "tz": "America/New_York",
                      "rejectUtcDay": true}
{"kind": "clockTime", "instant": "2026-07-15T20:12:00Z", "tz": "America/New_York",
                      "rejectUtcClock": true}
{"kind": "weekday",   "instant": "…", "tz": "…"}
{"kind": "regex",     "accept": "…", "reject": "…", "note": "…"}
```

Helper kinds expand to generated acceptance/rejection pattern sets so authors
don't hand-write date regexes:

- `civilDay` accepts any conventional reference to that calendar day *in the
  given tz* ("July 3", "Jul 3", "7/3", "the 3rd", "2026-07-03"); with
  `rejectUtcDay`, additionally **fails if the UTC calendar day is mentioned as
  the answer day** (only emitted when the two days differ — the schema requires
  the trap to be real).
- `clockTime` accepts conventional renderings of the local wall time ("4:12 pm",
  "4:12pm", "16:12"); `rejectUtcClock` symmetric.
- `weekday` accepts the local weekday name.
- `count` accepts the digit or spelled-out number adjacent to an optional unit
  regex; rejects other small numbers in the same slot.

Free-text grading is necessarily approximate; every helper errs toward
**accepting** unanticipated-but-correct phrasings (checks are anchored on the
facts, not the wording) and scenarios keep answers *checkable from timestamps
alone* (a count, a day, a wall time — not prose quality).

## Directions & scoring

- `nl2time` metric: fraction of scenarios (tagged with that direction) whose
  tool-call expectations all pass.
- `time2nl` metric: fraction whose response checks all pass.
- A scenario may feed both. Domain- and run-level rollups in `results/`.
