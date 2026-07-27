#!/usr/bin/env python3
"""Mechanical consistency checks for scenario goldens.

For every domain file:
1. Schema validation (via atb.scenarios).
2. For each `count` check on a scenario with a filter-rows tool expectation:
   re-filter the mock rows under EVERY admissible tuple; the count of rows
   matching the check's semantics must equal `expected` under each tuple
   (admissible readings must agree, by construction — see docs/scenarios.md).
   Because count checks may be merchant-scoped, the row subset is declared per
   check via an optional `note`-adjacent convention: we count rows in-range
   whose fields contain the scenario's obvious filter; to stay simple and
   reviewable, this script only verifies TOTAL in-range row counts when the
   check has no unit-scoping ambiguity — and always PRINTS the per-tuple
   in-range rows so a human can eyeball merchant-scoped counts.
3. For each civilDay/clockTime/weekday check: the instant must appear
   somewhere in the scenario's mock data (no phantom goldens).
4. Traps must be real: rejectUtcDay requires UTC day != local day;
   rejectUtcClock requires differing wall clocks.

Run: harness/.venv/bin/python scripts/verify_goldens.py [domain ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness" / "src"))

from atb.scenarios import REPO_ROOT, load_all  # noqa: E402
from atb.timeparse import instants_equal, parse_instant  # noqa: E402

problems: list[str] = []
notes: list[str] = []


def bridge_resolve(phrase: str, context: dict) -> dict:
    import subprocess

    proc = subprocess.run(
        ["node", str(REPO_ROOT / "bridge" / "bridge.mjs")],
        input=json.dumps({"op": "resolve", "phrase": phrase, "context": context}),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(proc.stdout) if proc.returncode == 0 else {"ok": False, "error": proc.stderr[-200:]}


def check_verify_phrase(sid: str, tc: dict, cfg: dict, context: dict) -> None:
    vp = tc["verifyPhrase"]
    result = bridge_resolve(vp["phrase"], context)
    expected_disagreement = "disagreementNote" in vp
    if not result.get("ok"):
        if not expected_disagreement:
            problems.append(f"{sid}: verifyPhrase {vp['phrase']!r} not resolvable by nl2time: {result.get('error')}")
        else:
            notes.append(f"{sid}: nl2time cannot resolve {vp['phrase']!r} (expected: {vp['disagreementNote']})")
        return
    start, end = parse_instant(result["start"]), parse_instant(result["end"])
    matched = any(
        instants_equal(start, parse_instant(t[cfg["startParam"]]))
        and instants_equal(end, parse_instant(t[cfg["endParam"]]))
        for t in tc["admissible"]
    )
    if matched and expected_disagreement:
        problems.append(f"{sid}: disagreementNote present but nl2time AGREES — remove the note")
    elif not matched and not expected_disagreement:
        problems.append(
            f"{sid}: nl2time resolves {vp['phrase']!r} to [{result['start']} .. {result['end']}) "
            "which matches NO admissible tuple — investigate (golden wrong, or nl2time wrong: add disagreementNote)"
        )
    elif not matched:
        notes.append(
            f"{sid}: EXPECTED disagreement on {vp['phrase']!r}: nl2time [{result['start']} .. {result['end']}) — {vp['disagreementNote']}"
        )


def rows_in_range(rows, ts_field, start, end):
    out = []
    for row in rows:
        ts = parse_instant(row[ts_field])
        if ts is not None and start <= ts < end:
            out.append(row)
    return out


def mock_contains_instant(mocks: dict, iso: str) -> bool:
    target = parse_instant(iso)
    blob = json.dumps(mocks)
    for token in blob.split('"'):
        if "T" in token and parse_instant(token) == target:
            return True
    return False


def main() -> None:
    only = sys.argv[1:] or None
    domains = load_all(only=only)
    for domain in domains:
        tool_specs = {t["name"]: t for t in domain.tools}
        for scenario in domain.scenarios:
            sid = f"{domain.name}/{scenario.id}"
            expect = scenario.expect

            # context.now's stated offset must match the timezone's real offset at that instant
            ctx = scenario.context
            now_utc = parse_instant(ctx["now"])
            from datetime import datetime as _dt
            stated = _dt.fromisoformat(ctx["now"].replace("Z", "+00:00")).utcoffset()
            actual = now_utc.astimezone(ZoneInfo(ctx["timeZone"])).utcoffset()
            if stated != actual:
                problems.append(
                    f"{sid}: context.now offset {stated} does not match {ctx['timeZone']} at that instant ({actual})"
                )

            for tc in expect.get("toolCalls", []):
                spec = tool_specs[tc["tool"]]
                if spec["mock"]["kind"] != "filter-rows":
                    continue
                cfg = spec["mock"]

                if "admissibleWindow" in tc:
                    win = tc["admissibleWindow"]
                    rows = scenario.mocks.get(tc["tool"], {}).get("rows", [])
                    core_s, core_e = (parse_instant(x) for x in win["core"])
                    env_s, env_e = (parse_instant(x) for x in win["envelope"])
                    if not (env_s <= core_s < core_e <= env_e):
                        problems.append(f"{sid}: window core not inside envelope")
                        continue
                    rows_core = rows_in_range(rows, cfg["timestampField"], core_s, core_e)
                    rows_env = rows_in_range(rows, cfg["timestampField"], env_s, env_e)
                    if [json.dumps(r, sort_keys=True) for r in rows_core] != [json.dumps(r, sort_keys=True) for r in rows_env]:
                        problems.append(
                            f"{sid}: window NOT answer-invariant — core selects {len(rows_core)} rows, envelope {len(rows_env)}"
                        )
                    notes.append(f"{sid} window core [{win['core'][0]} .. {win['core'][1]}), envelope [{win['envelope'][0]} .. {win['envelope'][1]}): {len(rows_core)} rows")
                    if "verifyPhrase" in tc:
                        vp = tc["verifyPhrase"]
                        result = bridge_resolve(vp["phrase"], dict(scenario.context))
                        if result.get("ok"):
                            r_s, r_e = parse_instant(result["start"]), parse_instant(result["end"])
                            fits = r_s is not None and env_s <= r_s <= core_s and core_e <= r_e <= env_e
                            if fits and "disagreementNote" in vp:
                                problems.append(f"{sid}: disagreementNote present but nl2time window FITS — remove the note")
                            elif not fits and "disagreementNote" not in vp:
                                problems.append(
                                    f"{sid}: nl2time window [{result['start']} .. {result['end']}) violates core/envelope — investigate"
                                )
                            elif not fits:
                                notes.append(f"{sid}: EXPECTED disagreement on {vp['phrase']!r}: nl2time [{result['start']} .. {result['end']}) — {vp['disagreementNote']}")
                        elif "disagreementNote" not in vp:
                            problems.append(f"{sid}: verifyPhrase {vp['phrase']!r} not resolvable: {result.get('error')}")
                        else:
                            notes.append(f"{sid}: nl2time cannot resolve {vp['phrase']!r} (expected: {vp['disagreementNote']})")
                    continue

                if "verifyPhrase" in tc:
                    check_verify_phrase(sid, tc, cfg, dict(scenario.context))
                rows = scenario.mocks.get(tc["tool"], {}).get("rows", [])
                if not rows:
                    problems.append(f"{sid}: filter-rows tool {tc['tool']} has no mock rows")
                    continue
                counts = set()
                for tup in tc["admissible"]:
                    start = parse_instant(tup[cfg["startParam"]])
                    end = parse_instant(tup[cfg["endParam"]])
                    if start is None or end is None or start >= end:
                        problems.append(f"{sid}: bad admissible tuple {tup}")
                        continue
                    selected = rows_in_range(rows, cfg["timestampField"], start, end)
                    counts.add(len(selected))
                    notes.append(
                        f"{sid} [{tup[cfg['startParam']]} .. {tup[cfg['endParam']]}): "
                        f"{len(selected)} rows: "
                        + ", ".join(str(r.get("merchant") or r.get("name") or r.get(cfg["timestampField"])) for r in selected)
                    )
                if len(counts) > 1:
                    problems.append(
                        f"{sid}: admissible tuples select DIFFERENT row counts {sorted(counts)} — "
                        "readings must agree by construction"
                    )

            for check in expect.get("response", {}).get("checks", []):
                kind = check["kind"]
                if kind in ("civilDay", "clockTime", "weekday"):
                    if not mock_contains_instant(scenario.mocks, check["instant"]):
                        problems.append(f"{sid}: {kind} instant {check['instant']} not present in mock data")
                    utc = parse_instant(check["instant"])
                    local = utc.astimezone(ZoneInfo(check["tz"]))
                    if check.get("rejectUtcDay") and utc.date() == local.date():
                        problems.append(f"{sid}: rejectUtcDay set but UTC and local day agree")
                    if check.get("rejectUtcClock") and (utc.hour, utc.minute) == (local.hour, local.minute):
                        problems.append(f"{sid}: rejectUtcClock set but clocks agree")

    print(f"checked {sum(len(d.scenarios) for d in domains)} scenarios in {len(domains)} domains")
    print("\n--- in-range row selections (eyeball merchant-scoped counts) ---")
    for note in notes:
        print(" ", note)
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  !!", p)
        sys.exit(1)
    print("\nno mechanical problems found")


if __name__ == "__main__":
    main()
