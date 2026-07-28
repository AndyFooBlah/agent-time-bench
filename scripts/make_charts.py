#!/usr/bin/env python3
"""Generate the blog charts as self-contained SVGs from sweep results.

Charts (light mode, validated palette: baseline #eb6834, +nl2time #2a78d6,
ink #0b0b0b/#52514e, surface #fcfcfb):
  blog/charts/args-dumbbell.svg  — NL→time tool-call accuracy per model
  blog/charts/resp-dumbbell.svg  — time→NL rendering accuracy per model

Run: harness/.venv/bin/python scripts/make_charts.py
"""

from __future__ import annotations

import glob
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODELS = [  # (glob key, display name, class note)
    ("google_gemma-4-26b-a4b-it", "Gemma 4 26B-A4B", "open · tiny"),
    ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite", "closed · cheap"),
    ("gemini-3.6-flash", "Gemini 3.6 Flash", "closed · mainstream"),
    ("deepseek_deepseek-v4-pro", "DeepSeek V4 Pro", "open · frontier"),
    ("moonshotai_kimi-k3", "Kimi K3", "open · frontier"),
    ("openai_gpt-5.6-sol", "GPT-5.6 Sol", "closed · frontier"),
    ("anthropic_claude-opus-5", "Claude Opus 5", "closed · frontier"),
]

BASELINE, TREATMENT = "#eb6834", "#2a78d6"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e8e7e3", "#fcfcfb"


def collect() -> dict:
    data: dict = defaultdict(lambda: defaultdict(lambda: {"a": [0, 0], "r": [0, 0]}))
    for f in glob.glob(os.path.join(ROOT, "results", "sweep-*.jsonl")):
        for line in open(f):
            row = json.loads(line)
            if "meta" in row:
                continue
            key = next((k for k, _, _ in MODELS if k in f), None)
            if key is None:
                continue
            bucket = data[key][row["run"]["condition"]]
            if "nl2time" in row["directions"] and row["nl2time_pass"] is not None:
                bucket["a"][1] += 1
                bucket["a"][0] += bool(row["nl2time_pass"])
            if row["time2nl_pass"] is not None:
                bucket["r"][1] += 1
                bucket["r"][0] += bool(row["time2nl_pass"])
    return data


def pct(pair):
    return 100.0 * pair[0] / pair[1] if pair[1] else None


def dumbbell(data: dict, metric: str, title: str, subtitle: str, out: str) -> None:
    rows = []
    for key, name, klass in MODELS:
        b, t = pct(data[key]["baseline"][metric]), pct(data[key]["nl2time"][metric])
        if b is None or t is None:
            continue
        rows.append((name, klass, b, t))
    rows.sort(key=lambda r: r[2])  # by baseline, ascending

    width, row_h, top, left, right = 860, 46, 96, 250, 70
    height = top + row_h * len(rows) + 56
    x0, x1 = left, width - right

    def x(v):
        return x0 + (x1 - x0) * v / 100.0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="system-ui, -apple-system, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>',
        f'<text x="24" y="34" font-size="19" font-weight="650" fill="{INK}">{title}</text>',
        f'<text x="24" y="56" font-size="13" fill="{INK2}">{subtitle}</text>',
        # legend
        f'<circle cx="{width-260}" cy="30" r="5" fill="{BASELINE}"/>'
        f'<text x="{width-250}" y="34" font-size="12" fill="{INK2}">baseline</text>'
        f'<circle cx="{width-170}" cy="30" r="5" fill="{TREATMENT}"/>'
        f'<text x="{width-160}" y="34" font-size="12" fill="{INK2}">+ nl2time tools</text>',
    ]
    for grid_value in (0, 25, 50, 75, 100):
        gx = x(grid_value)
        parts.append(f'<line x1="{gx}" y1="{top-18}" x2="{gx}" y2="{height-44}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{gx}" y="{height-24}" font-size="11" fill="{INK2}" text-anchor="middle">{grid_value}%</text>')

    for i, (name, klass, b, t) in enumerate(rows):
        cy = top + row_h * i + row_h // 2 - 8
        bx, tx = x(b), x(t)
        parts.append(f'<text x="{left-14}" y="{cy+1}" font-size="13" fill="{INK}" text-anchor="end" font-weight="600">{name}</text>')
        parts.append(f'<text x="{left-14}" y="{cy+16}" font-size="10.5" fill="{INK2}" text-anchor="end">{klass}</text>')
        lo, hi = min(bx, tx), max(bx, tx)
        if hi - lo > 1:
            parts.append(f'<line x1="{lo}" y1="{cy}" x2="{hi}" y2="{cy}" stroke="{GRID}" stroke-width="2"/>')
        if abs(tx - bx) < 3:  # equal values: baseline ring around treatment dot
            parts.append(f'<circle cx="{tx}" cy="{cy}" r="11" fill="none" stroke="{BASELINE}" stroke-width="2.5"/>')
            parts.append(f'<circle cx="{tx}" cy="{cy}" r="6" fill="{TREATMENT}" stroke="{SURFACE}" stroke-width="2"/>')
            parts.append(f'<text x="{tx-18}" y="{cy+4}" font-size="11.5" fill="{INK}" font-weight="650" text-anchor="end">{t:.0f}%</text>')
            parts.append(f'<text x="{tx+18}" y="{cy+4}" font-size="11.5" fill="{INK2}" text-anchor="start">no change</text>')
            continue
        # markers with 2px surface ring (overlap-safe)
        parts.append(f'<circle cx="{bx}" cy="{cy}" r="7" fill="{BASELINE}" stroke="{SURFACE}" stroke-width="2"/>')
        parts.append(f'<circle cx="{tx}" cy="{cy}" r="7" fill="{TREATMENT}" stroke="{SURFACE}" stroke-width="2"/>')
        # direct labels, ink not series color
        b_anchor, b_dx = ("end", -12) if tx >= bx else ("start", 12)
        t_anchor, t_dx = ("start", 12) if tx >= bx else ("end", -12)
        if abs(tx - bx) < 34:  # too close: stack labels
            parts.append(f'<text x="{bx}" y="{cy-12}" font-size="11.5" fill="{INK2}" text-anchor="middle">{b:.0f}%</text>')
            parts.append(f'<text x="{tx}" y="{cy+22}" font-size="11.5" fill="{INK}" font-weight="650" text-anchor="middle">{t:.0f}%</text>')
        else:
            parts.append(f'<text x="{bx+b_dx}" y="{cy+4}" font-size="11.5" fill="{INK2}" text-anchor="{b_anchor}">{b:.0f}%</text>')
            parts.append(f'<text x="{tx+t_dx}" y="{cy+4}" font-size="11.5" fill="{INK}" font-weight="650" text-anchor="{t_anchor}">{t:.0f}%</text>')
    parts.append("</svg>")

    path = os.path.join(ROOT, "blog", "charts", out)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("\n".join(parts))
    print("wrote", path)


def main() -> None:
    data = collect()
    dumbbell(
        data, "a",
        "Correct time bounds in tool calls, by model",
        "78 graded scenarios per run; repeats pooled. Single-turn agents, identical prompts; the only difference is the nl2time tools + skill.",
        "args-dumbbell.svg",
    )
    dumbbell(
        data, "r",
        "Correct rendering of timestamps in answers, by model",
        "100 scenarios per run; repeats pooled. Deterministic acceptance checks (local day, wall time, counts) with UTC-reading rejects.",
        "resp-dumbbell.svg",
    )


if __name__ == "__main__":
    main()
