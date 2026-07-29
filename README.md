# agent-time-bench

How well do LLM agents handle date/time — in the tool calls they make and in the answers they give?

Agents constantly move time across three representations: the user's words ("last week"), tool arguments (ISO 8601 UTC), and rendered answers ("you paid it on June 1st"). Each hop crosses a timezone, a locale convention, and an ambiguity policy. This benchmark measures those hops in situ: 10 domains × 10 single-turn scenarios with mocked tools, graded on (a) the time bounds the agent actually passed and (b) how it rendered returned timestamps for the user.

The benchmark is treatment-neutral; its first experiment measures the lift from giving agents deterministic time tools backed by [nl2time](https://github.com/AndyFooBlah/nl2time) plus a usage skill, versus a baseline where the model does time math itself.

- [docs/design.md](docs/design.md) — what is measured and why
- [docs/scenarios.md](docs/scenarios.md) — scenario format and grading semantics
- [docs/framework-choice.md](docs/framework-choice.md) — why ADK + a thin custom runner
- `scenarios/` — the corpus (goldens hand-derived AND mechanically cross-checked: `scripts/verify_goldens.py`)
- `harness/` — Python (uv) ADK harness: `uv run atb run --model gemini-3.5-flash-lite`
- `bridge/` — node bridge exposing nl2time to the Python harness and the verifier

Status: full corpus (10 domains × 10 scenarios; goldens hand-derived, mechanically verified, blind-audited — see docs/ground-truth.md) and a completed study across 7 models (tiny open-weights → closed frontier): with deterministic time tools, tool-call bounds reach 94–98% and timestamp rendering 86–98%; a ~4B-active open model goes 14% → 94% on bounds — see [docs/results-flash-lite.md](docs/results-flash-lite.md) and the [blog draft](blog/post.md). Authoring + runs surfaced 8 nl2time issues (#17–#24), fixed in nl2time 0.3.1.
