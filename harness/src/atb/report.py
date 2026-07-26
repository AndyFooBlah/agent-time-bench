"""Aggregate result JSONL files into per-run / per-direction / per-domain accuracy."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if "meta" not in row:
                rows.append(row)
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple, dict[str, list]] = defaultdict(lambda: {"nl2time": [], "time2nl": [], "errors": 0})
    for row in rows:
        key = (row["run"]["model"], row["run"]["condition"], row["run"].get("skill"))
        b = buckets[key]
        if row.get("error"):
            b["errors"] += 1
        if "nl2time" in row["directions"] and row["nl2time_pass"] is not None:
            b["nl2time"].append(bool(row["nl2time_pass"]))
        if "time2nl" in row["directions"] and row["time2nl_pass"] is not None:
            b["time2nl"].append(bool(row["time2nl_pass"]))

    def acc(xs: list[bool]) -> str:
        return f"{sum(xs)}/{len(xs)} = {100 * sum(xs) / len(xs):.1f}%" if xs else "n/a"

    out: dict[str, Any] = {}
    for (model, condition, skill), b in sorted(buckets.items()):
        out[f"{model} | {condition}" + (f" | {skill}" if skill else "")] = {
            "nl2time": acc(b["nl2time"]),
            "time2nl": acc(b["time2nl"]),
            "errors": b["errors"],
        }
    return out


def per_domain(rows: list[dict[str, Any]], direction: str) -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if direction in row["directions"] and row[f"{direction}_pass"] is not None:
            table[row["domain"]][row["run"]["condition"]].append(bool(row[f"{direction}_pass"]))
    return {
        domain: {
            cond: f"{sum(xs)}/{len(xs)}" for cond, xs in sorted(conds.items())
        }
        for domain, conds in sorted(table.items())
    }


def failures(rows: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        failed_dirs = [
            d for d in row["directions"]
            if row.get(f"{d}_pass") is False
        ]
        if failed_dirs or row.get("error"):
            out.append(
                {
                    "scenario": row["scenario"],
                    "condition": row["run"]["condition"],
                    "failed": failed_dirs,
                    "error": (row.get("error") or "")[:200] or None,
                    "tool_results": [r for r in row["tool_results"] if not r["passed"]],
                    "check_results": [r for r in row["check_results"] if not r["passed"]],
                    "response": row["response"][:300],
                }
            )
    return out[:limit]
