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

    for name in ("report", "failures"):
        p = sub.add_parser(name)
        p.add_argument("files", nargs="+", type=Path)

    sub.add_parser("validate", help="Validate all scenario files against the schema")

    args = parser.parse_args()

    if args.command == "validate":
        domains = load_all()
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
    if args.command == "report":
        print(json.dumps(summarize(rows), indent=2))
        for direction in ("nl2time", "time2nl"):
            print(f"\nper-domain ({direction}):")
            print(json.dumps(per_domain(rows, direction), indent=2))
    else:
        print(json.dumps(failures(rows), indent=2))
