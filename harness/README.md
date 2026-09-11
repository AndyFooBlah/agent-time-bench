# atb — the agent-time-bench harness

Python (uv) package that assembles one Google ADK `LlmAgent` per scenario,
runs it single-turn against mocked domain tools, records the transcript, and
grades it. See the repository [README](../README.md#quickstart) for setup and
credentials, and [`docs/design.md`](../docs/design.md) for what is measured.

## Layout

| Module | Role |
|---|---|
| `atb/cli.py` | `atb run / report / compare / failures / regrade / validate`; loads `<repo>/.env` |
| `atb/scenarios.py` | Loads and schema-validates `scenarios/*.json` |
| `atb/agent.py` | Builds the agent: prompt template (`prompts/`), optional skill (`skills/`), mocked tools, optional nl2time tools; `litellm:<provider>/<model>` selects ADK's LiteLLM wrapper |
| `atb/mocktools.py` | Domain tools as ADK `BaseTool`s; `filter-rows` mocks apply the agent's real bounds to canned rows |
| `atb/nl2time_tools.py` | `resolve_timephrase` and `describe_time`, backed by `bridge/bridge.mjs` (one Node subprocess per call) |
| `atb/runner.py` | Concurrency, per-row recording, JSONL output |
| `atb/grading.py`, `atb/timeparse.py` | Pure-function graders (unit-tested in `tests/`) |
| `atb/report.py` | Aggregation: `summarize`, `per_domain`, `compare_conditions`, `failures` |

## Commands

```bash
cd harness && uv sync                       # once
uv run atb validate [domain ...]            # corpus schema check
uv run atb run --model <id> [--conditions baseline nl2time] [--prompt baseline-v2] [--skill nl2time-v3] \
               [--domains d1 d2] [--limit N] [--concurrency 4] [--out file.jsonl] [--label rN]
uv run atb report   <run.jsonl ...>         # accuracy per (model, condition), then per domain
uv run atb compare  <run.jsonl ...>         # baseline vs nl2time, paired by scenario
uv run atb failures <run.jsonl ...>
uv run atb regrade  <run.jsonl ...> [--out regraded.jsonl]   # re-score recorded transcripts with current graders
uv run pytest tests -q
```

From the repo root, prefix with `uv run --project harness …` instead of `cd`.

## Output rows

One JSONL file per run: a `{"meta": …}` header, then one row per scenario ×
condition with `run`, `domain`, `scenario`, `directions`, `user`, `tool_calls`,
`response`, `error`, `latency_s`, and the grading verdicts `nl2time_pass`
(tool-call time bounds; `null` when the scenario does not grade that direction)
and `time2nl_pass` (rendered timestamps), plus per-check diagnostics. Rows with
a non-null `error` are counted as failures.

## Dependencies

`google-adk` (agent runtime, Gemini models), `litellm` (other providers through
`google.adk.models.lite_llm.LiteLlm`), `jsonschema`. The lock file is the
source of truth (`uv sync --frozen` in CI); `pip-audit` runs clean against it.
