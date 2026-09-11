# results/

Run artifacts from `atb run` (one JSONL per run: a `meta` header row, then one
graded row per scenario × condition — transcript, tool calls, grading verdicts).

## What is committed, and why

| Path | Committed? | Purpose |
|---|---|---|
| `sweep-<model>-r<N>.jsonl` | **yes** | The published 7-model study (2026-07-28; prompt `baseline-v2`, skill `nl2time-v3`, nl2time 0.3.1). `scripts/make_charts.py` and the table in `docs/results-flash-lite.md` are computed from exactly these files. |
| `invalid/` | yes, annotated | Runs excluded from the study — see [`invalid/README.md`](invalid/README.md) for why each one was discarded. Never read by the chart script. |
| `run1-summary.md` | yes | Narrative record of the first flash-lite run. |
| `run*-*.jsonl`, `smoke-*.jsonl`, `<timestamp>-<model>.jsonl` | no (gitignored) | Iteration runs, smoke tests, and default-named output of local `atb run` invocations. Scratch. |

`.gitignore` implements this: `results/**/*.jsonl` is ignored except
`results/sweep-*.jsonl` and `results/invalid/*.jsonl`. If you produce a run
that should become part of the published record, name it `sweep-…` (or pass
`--out results/sweep-<slug>-r<N>.jsonl`, as `scripts/sweep.sh` does) and add it
to the model list in `scripts/make_charts.py`.

## Reproducing the charts and tables

```bash
uv run --project harness python scripts/make_charts.py   # rewrites blog/charts/*.svg
uv run --project harness atb report results/sweep-*.jsonl # pooled summary
uv run --project harness atb regrade results/sweep-gemini-3.6-flash-r1.jsonl  # re-score with current graders
```

The committed SVGs are byte-identical to what `make_charts.py` produces from
the committed sweep rows (verified by md5 at commit time).

## Privacy / hygiene of committed rows

Rows are model transcripts over fictional mock data; there are no keys or
third-party personal data in them. The `error` field of rows whose provider
call failed (timeouts, OpenRouter 5xx, malformed tool calls from small models)
has been reduced to its first line, with local filesystem paths, provider
request ids, and account URLs redacted. Grading fields are untouched, so the
sanitized files reproduce the published numbers exactly. Error rows are
counted as failures, as described in `docs/results-flash-lite.md`.
