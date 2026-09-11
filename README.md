# agent-time-bench

How well do LLM agents handle date/time — in the tool calls they make and in the answers they give?

Agents constantly move time across three representations: the user's words ("last week"), tool arguments (ISO 8601 UTC), and rendered answers ("you paid it on June 1st"). Each hop crosses a timezone, a locale convention, and an ambiguity policy. This benchmark measures those hops in situ: 10 domains × 10 single-turn scenarios with mocked tools, graded on (a) the time bounds the agent actually passed and (b) how it rendered returned timestamps for the user.

The benchmark is treatment-neutral; its first experiment measures the lift from giving agents deterministic time tools backed by [nl2time](https://github.com/AndyFooBlah/nl2time) plus a usage skill, versus a baseline where the model does time math itself.

- [docs/design.md](docs/design.md) — what is measured and why
- [docs/scenarios.md](docs/scenarios.md) — scenario format and grading semantics
- [docs/framework-choice.md](docs/framework-choice.md) — why ADK + a thin custom runner
- `scenarios/` — the corpus (goldens hand-derived AND mechanically cross-checked: `scripts/verify_goldens.py`)
- `harness/` — Python (uv) ADK harness and the `atb` CLI ([harness/README.md](harness/README.md))
- `bridge/` — Node bridge exposing nl2time to the Python harness and the verifier
- `results/` — the published sweep rows the charts are computed from ([results/README.md](results/README.md))

Status: full corpus (10 domains × 10 scenarios; goldens hand-derived, mechanically verified, blind-audited — see docs/ground-truth.md) and a completed study across 7 models (tiny open-weights → closed frontier): with deterministic time tools, tool-call bounds reach 94–98% and timestamp rendering 86–98%; a ~4B-active open model goes 14% → 94% on bounds — see [docs/results-flash-lite.md](docs/results-flash-lite.md) and the [blog post](https://andrewbrook.dev/writing/agents-and-time/) (source in [blog/post.md](blog/post.md)). Authoring + runs surfaced 8 nl2time issues (#17–#24); 7 of 8 were fixed in nl2time 0.3.1 ([#23](https://github.com/AndyFooBlah/nl2time/issues/23) is still open).

## Quickstart

Prerequisites: **Node ≥ 22** (the bridge uses the Temporal polyfill through nl2time), **[uv](https://docs.astral.sh/uv/)** (manages Python 3.12 and the harness venv), and credentials for at least one model provider.

```bash
git clone https://github.com/AndyFooBlah/agent-time-bench && cd agent-time-bench

# 1. Bridge: nl2time for the harness's time tools and for the golden verifier
(cd bridge && npm ci && npm test)

# 2. Harness: creates harness/.venv and installs the `atb` CLI
(cd harness && uv sync)

# 3. Everything that needs no model credentials
uv run --project harness pytest harness/tests -q         # grader unit tests
uv run --project harness atb validate                    # schema-check the corpus
uv run --project harness python scripts/verify_goldens.py  # mechanical + nl2time cross-check of goldens
```

### Credentials

The harness reads `<repo root>/.env` (`KEY=value` lines, gitignored, never overriding variables already in your shell) and the process environment. Nothing is logged or written to `results/`.

| Models | What to set |
|---|---|
| Gemini via the Gemini Developer API | `GOOGLE_API_KEY=…` ([get a key](https://ai.google.dev/gemini-api/docs/api-key)) |
| Gemini via Vertex AI (ADC) | `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_PROJECT=<your project>`, `GOOGLE_CLOUD_LOCATION=global`, after `gcloud auth application-default login` |
| Anything else, via LiteLLM (`--model litellm:<provider>/<model>`) | the provider's own variable, e.g. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY` (`litellm:openrouter/moonshotai/kimi-k3`) |

### Smoke run, then a full run

```bash
# One scenario per domain, both conditions (~20 model calls). Output goes to results/<timestamp>-<model>.jsonl (gitignored).
uv run --project harness atb run --model gemini-3.5-flash-lite --limit 1

# The frozen study config: prompt baseline-v2, skill nl2time-v3, all 100 scenarios × 2 conditions
uv run --project harness atb run --model gemini-3.5-flash-lite --prompt baseline-v2 --skill nl2time-v3 \
  --out results/my-run.jsonl

uv run --project harness atb report  results/my-run.jsonl   # accuracy per condition, per domain
uv run --project harness atb compare results/my-run.jsonl   # scenarios the treatment fixed / regressed
uv run --project harness atb failures results/my-run.jsonl  # failing rows with transcripts
uv run --project harness atb regrade  results/my-run.jsonl  # re-score saved transcripts with the current graders (free)
```

`scripts/sweep.sh` and `scripts/smoke-models.sh` are the exact invocations behind the published 7-model study; `scripts/make_charts.py` rebuilds `blog/charts/*.svg` from `results/sweep-*.jsonl`. Model IDs change quickly — check the [Gemini model list](https://ai.google.dev/gemini-api/docs/models) (`gemini-3.5-flash-lite` was the current Flash-Lite at the time of writing).

## Licensing

- **Code** — everything under `harness/`, `bridge/`, `scripts/`, `schema/`, and `.github/` — is licensed under the Apache License 2.0 ([LICENSE](LICENSE)).
- **Content** — the scenario corpus (`scenarios/`), documentation (`docs/`), the blog source and charts (`blog/`), prompts and skills (`prompts/`, `skills/`), and the published run data (`results/`) — is licensed under Creative Commons Attribution 4.0 International ([LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0); summary at [creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/)). Attribute as "agent-time-bench by Andrew Brook" with a link to this repository.
