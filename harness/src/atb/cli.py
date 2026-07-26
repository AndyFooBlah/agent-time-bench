"""CLI: `atb run`, `atb report`, `atb failures`, `atb validate`."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from .report import failures, load_rows, per_domain, summarize
from .runner import run_matrix
from .scenarios import REPO_ROOT, load_all


def main() -> None:
    parser = argparse.ArgumentParser(prog="atb")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the benchmark matrix")
    run_p.add_argument("--model", default="gemini-3.5-flash-lite")
    run_p.add_argument("--conditions", nargs="+", default=["baseline", "nl2time"], choices=["baseline", "nl2time"])
    run_p.add_argument("--skill", default="nl2time-v1", help="Skill fragment (skills/<name>.md) for the nl2time condition")
    run_p.add_argument("--domains", nargs="*", help="Domain names (default: all)")
    run_p.add_argument("--out", default=None, help="Output JSONL (default: results/<ts>-<model>.jsonl)")
    run_p.add_argument("--concurrency", type=int, default=4)

    for name in ("report", "failures", "regrade"):
        p = sub.add_parser(name)
        p.add_argument("files", nargs="+", type=Path)
        if name == "regrade":
            p.add_argument("--out", type=Path, help="Write regraded rows to this JSONL")

    val_p = sub.add_parser("validate", help="Validate scenario files against the schema")
    val_p.add_argument("domains", nargs="*", help="Domain names (default: all)")

    args = parser.parse_args()

    if args.command == "validate":
        domains = load_all(only=args.domains or None)
        total = sum(len(d.scenarios) for d in domains)
        print(f"OK: {len(domains)} domains, {total} scenarios validate.")
        return

    if args.command == "run":
        domains = load_all(only=args.domains)
        if not domains:
            raise SystemExit("no matching domains")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = Path(args.out) if args.out else REPO_ROOT / "results" / f"{stamp}-{args.model.replace('/', '_').replace(':', '_')}.jsonl"
        rows = asyncio.run(
            run_matrix(domains, args.model, args.conditions, args.skill, out, args.concurrency)
        )
        print(f"\nwrote {len(rows)} rows to {out}\n")
        print(json.dumps(summarize(rows), indent=2))
        return

    rows = load_rows(args.files)
    if args.command == "regrade":
        # Re-score recorded transcripts with the CURRENT graders and scenario
        # expectations — grader iteration without model cost.
        from .grading import grade_scenario

        index = {
            (d.name, s.id): s for d in load_all() for s in d.scenarios
        }
        regraded = []
        for row in rows:
            scenario = index[(row["domain"], row["scenario"])]
            graded = grade_scenario(scenario.expect, row["tool_calls"], row["response"], dict(scenario.context))
            regraded.append({**row, **graded})
        if args.out:
            with args.out.open("w") as fh:
                for row in regraded:
                    fh.write(json.dumps(row) + "\n")
            print(f"wrote {len(regraded)} regraded rows to {args.out}")
        print(json.dumps(summarize(regraded), indent=2))
        return

    if args.command == "report":
        print(json.dumps(summarize(rows), indent=2))
        for direction in ("nl2time", "time2nl"):
            print(f"\nper-domain ({direction}):")
            print(json.dumps(per_domain(rows, direction), indent=2))
    else:
        print(json.dumps(failures(rows), indent=2))
