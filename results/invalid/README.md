# results/invalid/ — runs excluded from the published study

These two files are the **direct-Anthropic** Claude Opus 5 runs
(`--model litellm:anthropic/claude-opus-5`) attempted on 2026-07-28 during the
multi-model sweep. They are kept for provenance and are not read by
`scripts/make_charts.py` (it globs `results/sweep-*.jsonl` only) nor counted in
any table.

| File | Rows | Why excluded |
|---|---|---|
| `sweep-litellm_anthropic_claude-opus-5-r1.jsonl` | 200/200 completed, 0 errors | Completed cleanly, but the paired repeat (r2) stalled, so the direct-Anthropic pair was abandoned as a set and the model was re-run through OpenRouter (`results/sweep-litellm_openrouter_anthropic_claude-opus-5-r{1,2}.jsonl`) — those two repeats are the published Opus 5 numbers. Keeping r1 alongside the OpenRouter runs would have mixed two routing paths for one model. |
| `sweep-litellm_anthropic_claude-opus-5-r2.jsonl` | 160/200 completed, 40 error rows | The Anthropic account's credit balance was exhausted partway through; the remaining 40 scenario executions returned a billing error and were never graded. This is the "exhausted Anthropic balance" stall mentioned in `docs/results-flash-lite.md`. |

The `error` field of the 40 failed rows has been reduced to a one-line
summary; the original tracebacks (which embedded local paths and provider
request ids) were stripped. Grading fields are unchanged.
