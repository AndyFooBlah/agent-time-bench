# Eval framework choice

Decision (2026-07-26): **Google ADK as the agent harness, driven by a thin
custom runner that owns scenarios, mocks, conditions, and grading.** EvalBench
rejected; ADK's built-in eval and Inspect AI documented below as the near-miss
alternatives. Sources verified against live docs on the decision date.

## Requirements that drove the choice

1. Grade **only the time-bearing args** of tool calls, as instants, with
   tolerance semantics and admissible-tuple alternatives (docs/scenarios.md).
2. Grade the **final NL response's rendering of timestamps** returned by mocks.
3. **Filtering mocks**: canned rows filtered by the agent's actual bounds.
4. Run matrix = model × condition (baseline / nl2time) × skill version, with
   per-scenario contexts (now/tz/locale) injected into the system prompt.
5. Model-agnostic: Gemini today, OpenAI/Anthropic later, no infra coupling.

## EvalBench — rejected

[EvalBench](https://github.com/GoogleCloudPlatform/evalbench) (used in
weatherbot's NL2SQL evals) is a **database evaluation framework**: its runners
generate SQL, execute it against live databases, and score query results
(DQL/DML/DDL); datasets, config, and scorers are all organized around that
loop. It has pluggable scorers, but nothing in it evaluates agent tool
trajectories — for this benchmark we would replace the runner, the dataset
mapping, and the scorers, i.e. everything of value. Wrong shape, not a close
call.

## ADK built-in eval (`adk eval` / AgentEvaluator) — partial fit, not adopted

ADK ≥2.x has a real eval system ([adk.dev/evaluate](https://adk.dev/evaluate/)):
EvalSet/EvalCase schemas, pytest integration, and — decisively — a
[custom-metrics hook](https://adk.dev/evaluate/custom_metrics/) receiving actual
invocations (tool calls with args + final response), which could host our
graders. What it does *not* give us cheaply:

- Built-in `tool_trajectory_avg_score` is **exact-match** on whole tool calls —
  unusable here; our graders are custom code under either design.
- One evalset assumes one fixed agent; our tools/mocks/contexts vary per
  domain and scenario, so everything would thread through session-state
  seeding and instruction providers — machinery serving the format, not the
  benchmark.
- The run matrix (model × condition × skill) and filtering-mock control live
  outside its model anyway.

So ADK-native eval would give us storage/reporting we then fight, while the
part we must write (graders) is identical. We keep the door open: graders are
plain functions over (tool calls, final text) and can be registered as ADK
custom metrics later if CI-via-`adk eval` becomes attractive.

## Inspect AI — credible, deferred

[Inspect](https://inspect.aisi.org.uk/) has the most ergonomic scorer model and
first-class multi-provider support, but using ADK as the agent harness means
integrating through its agent bridge, and mocked-tool control is weakest across
that seam. If this benchmark is later published for others to run against
arbitrary agent stacks, porting the canonical scenario format to an Inspect
task is the natural move — the scenario JSON is deliberately
framework-neutral for exactly that reason.

## What we build (thin runner)

- Canonical scenario JSON (docs/scenarios.md) — the benchmark artifact proper,
  independent of any framework.
- `harness/`: Python (uv), `google-adk` (pinned; 2.5.0 at decision time) using
  the **Runner API directly** — per-scenario agent assembly (domain tools as
  dynamic mock tools, optional nl2time tools, skill fragment, context-bearing
  instruction), single-turn execution, event capture.
- Graders as pure functions; results as JSONL + aggregate summaries.
- Models: Gemini via native model strings (`GOOGLE_API_KEY`, or Vertex via ADC
  with `GOOGLE_GENAI_USE_VERTEXAI=TRUE` and `GOOGLE_CLOUD_LOCATION=global`);
  other vendors via `google.adk.models.lite_llm.LiteLlm`. Nothing in scenarios
  or grading is Gemini-specific.

## Prior-art positioning (for the eventual writeup)

Existing temporal benchmarks grade parsing/arithmetic in isolation
(PRIMETIME [arXiv:2504.16155](https://arxiv.org/abs/2504.16155), DateLogicQA
[arXiv:2412.13377](https://arxiv.org/abs/2412.13377)), reasoning loops with
tools (Time Puzzles [arXiv:2601.07148](https://arxiv.org/pdf/2601.07148)), or
function calls by exact AST match with dates as incidental strings (BFCL v4,
[gorilla.cs.berkeley.edu](https://gorilla.cs.berkeley.edu/leaderboard.html)).
None grade *resolved absolute time bounds in tool arguments* (with tolerance,
anchored to an injected "now") plus *timestamp rendering in the final
response*. That is this benchmark's contribution.
