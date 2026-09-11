#!/usr/bin/env python3
"""Blind-audit tooling for golden validation.

`strip` mode: write goldens-stripped copies of every domain file (context, user
utterance, tool specs, mock rows — but NO expect/rationale) for independent
re-derivation by auditors who must not see the answers.

`compare` mode: given an auditor's derivation JSON (list of {id, toolCalls:
[{tool, tuples:[{param: iso}]}]}), check each derived tuple set against the
golden admissible sets: PASS if every golden tuple is derived (as instants) or
explicitly listed by the auditor as a defensible alternative, and no derived
tuple is missing from the goldens (which would mean the goldens are too
narrow). Prints a per-scenario verdict; disagreements are for human review.

Run from repo root:
  uv run --project harness python scripts/blind_audit.py strip <outdir>
  uv run --project harness python scripts/blind_audit.py compare <derivations.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness" / "src"))

from atb.scenarios import SCENARIOS_DIR, load_all  # noqa: E402
from atb.timeparse import instants_equal, parse_instant  # noqa: E402


def strip(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        blinded = {
            "domain": data["domain"],
            "description": data["description"],
            "tools": data["tools"],
            "scenarios": [
                {
                    "id": s["id"],
                    "context": s["context"],
                    "user": s["user"],
                    "mocks": s.get("mocks", {}),
                    "gradedToolArgs": [
                        {"tool": tc["tool"], "graded": tc["graded"]}
                        for tc in s.get("expect", {}).get("toolCalls", [])
                    ],
                }
                for s in data["scenarios"]
            ],
        }
        (outdir / path.name).write_text(json.dumps(blinded, indent=2) + "\n")
    print(f"blinded files in {outdir}")


def tuples_equal(a: dict, b: dict) -> bool:
    if set(a) != set(b):
        return False
    for k in a:
        ia, ib = parse_instant(a[k]), parse_instant(b[k])
        if ia is None or ib is None or not instants_equal(ia, ib):
            return False
    return True


def compare(derivation_path: Path) -> None:
    derived = {d["id"]: d for d in json.loads(derivation_path.read_text())}
    golden = {
        s.id: s for domain in load_all() for s in domain.scenarios
    }
    agree = missing = 0
    for sid, d in sorted(derived.items()):
        scenario = golden.get(sid)
        if scenario is None:
            print(f"?? {sid}: unknown scenario")
            continue
        expectations = scenario.expect.get("toolCalls", [])
        verdicts = []
        for tc in expectations:
            dv = next((x for x in d.get("toolCalls", []) if x["tool"] == tc["tool"]), None)
            if dv is None:
                verdicts.append(f"{tc['tool']}: NOT DERIVED")
                continue
            golden_tuples = tc["admissible"]
            derived_tuples = dv.get("tuples", [])
            g_not_d = [g for g in golden_tuples if not any(tuples_equal(g, dd) for dd in derived_tuples)]
            d_not_g = [dd for dd in derived_tuples if not any(tuples_equal(dd, g) for g in golden_tuples)]
            if not g_not_d and not d_not_g:
                verdicts.append(f"{tc['tool']}: MATCH")
            else:
                parts = []
                if g_not_d:
                    parts.append(f"golden-not-derived {g_not_d}")
                if d_not_g:
                    parts.append(f"derived-not-golden {d_not_g}")
                verdicts.append(f"{tc['tool']}: DISAGREE ({'; '.join(parts)})")
        line = "; ".join(verdicts) if verdicts else "(no graded tool calls)"
        status = "OK " if all("MATCH" in v for v in verdicts) or not verdicts else "!! "
        if status == "OK ":
            agree += 1
        else:
            missing += 1
        print(f"{status}{sid}: {line}")
    print(f"\n{agree} agree, {missing} to review")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "strip":
        strip(Path(sys.argv[2]))
    elif mode == "compare":
        compare(Path(sys.argv[2]))
    else:
        raise SystemExit("mode must be strip|compare")
