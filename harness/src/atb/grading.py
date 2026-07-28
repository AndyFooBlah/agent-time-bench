"""Graders: tool-call argument grading (NL→time) and response checks (time→NL).

Pure functions over (recorded tool calls, final response text) so they are
framework-independent (registrable later as ADK custom metrics if wanted).
Acceptance patterns err toward ACCEPTING unanticipated-but-correct phrasings;
rejection patterns are limited to unambiguous wrong renderings.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .timeparse import end_matches, instants_equal, parse_instant

NUMBER_WORDS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen", "twenty",
]

MONTHS = [
    None, "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
]

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[*_`#]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- tool calls

def _window_matches(window_spec: dict[str, Any], args: dict[str, Any]) -> tuple[bool, str]:
    """core ⊆ [start, end) ⊆ envelope — for fuzzy window families ('Tuesday
    night', 'this morning') where enumerating tuples is hopeless. The verifier
    guarantees rows(core) == rows(envelope), so every admissible window gives
    the same answer."""
    start = parse_instant(args.get(window_spec["startParam"]))
    end = parse_instant(args.get(window_spec["endParam"]))
    if start is None or end is None:
        return False, "unparseable bounds"
    core_s, core_e = (parse_instant(x) for x in window_spec["core"])
    env_s, env_e = (parse_instant(x) for x in window_spec["envelope"])
    if not (start <= core_s and end >= core_e):
        return False, "does not contain core"
    if not (start >= env_s and end <= env_e):
        return False, "exceeds envelope"
    return True, "window ok"


def grade_tool_call(expectation: dict[str, Any], calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Pass if ANY call to the tool matches ONE admissible tuple on ALL graded
    args, or (for window expectations) satisfies core ⊆ window ⊆ envelope."""
    tool = expectation["tool"]
    relevant = [c for c in calls if c["tool"] == tool]

    window_spec = expectation.get("admissibleWindow")
    if window_spec is not None:
        attempts = []
        for call in relevant:
            ok, why = _window_matches(window_spec, call["args"])
            if ok:
                return {"tool": tool, "passed": True, "matched": "window", "call_args": call["args"]}
            attempts.append({"args": call["args"], "why": why})
        return {"tool": tool, "passed": False, "called": bool(relevant), "calls": [c["args"] for c in relevant], "attempts": attempts[:6]}

    graded = expectation["graded"]
    kinds = expectation["argKinds"]
    attempts = []
    for call in relevant:
        for tuple_index, admissible in enumerate(expectation["admissible"]):
            mismatches = []
            for arg in graded:
                ok = _arg_matches(kinds.get(arg, "string"), call["args"].get(arg), admissible[arg])
                if not ok:
                    mismatches.append({"arg": arg, "actual": call["args"].get(arg), "golden": admissible[arg]})
            attempts.append({"tuple": tuple_index, "mismatches": mismatches})
            if not mismatches:
                return {"tool": tool, "passed": True, "matched_tuple": tuple_index, "call_args": call["args"]}
    return {
        "tool": tool,
        "passed": False,
        "called": bool(relevant),
        "calls": [c["args"] for c in relevant],
        "attempts": attempts[:6],
    }


def _arg_matches(kind: str, actual: Any, golden: str) -> bool:
    if kind in ("instant", "instant-start", "instant-end"):
        actual_i = parse_instant(actual)
        golden_i = parse_instant(golden)
        if actual_i is None or golden_i is None:
            return False
        if kind == "instant-end":
            return end_matches(actual_i, golden_i)
        return instants_equal(actual_i, golden_i)
    if kind == "date":
        return isinstance(actual, str) and actual.strip() == golden
    return isinstance(actual, str) and actual.strip().lower() == golden.lower()


# ------------------------------------------------------------ response checks

def _local(dt_iso: str, tz: str) -> datetime:
    return parse_instant(dt_iso).astimezone(ZoneInfo(tz))  # type: ignore[union-attr]


def _day_patterns(local: datetime) -> list[str]:
    month = MONTHS[local.month]
    mon3 = month[:3]
    d = local.day
    ordinal = {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd", 31: "st"}.get(d, "th")
    return [
        rf"\b(?:{month}|{mon3}\.?)\s+{d}(?:{ordinal})?\b",
        rf"\b{d}(?:{ordinal})?\s+(?:of\s+)?(?:{month}|{mon3}\.?)\b",
        rf"\bthe\s+{d}{ordinal}\b",
        rf"\b{local.month}/{d}(?:/(?:{local.year}|{local.year % 100}))?\b",
        rf"\b{local.month:02d}/{d:02d}(?:/(?:{local.year}|{local.year % 100}))?\b",
        rf"\b{local.year}-{local.month:02d}-{d:02d}\b",
    ]


def _strict_day_patterns(local: datetime) -> list[str]:
    """Unambiguous forms only — safe to use as REJECT patterns."""
    return _day_patterns(local)[:2] + _day_patterns(local)[3:]


def _deictic_patterns(delta_days: int, weekday: int) -> list[str]:
    """Relative renderings of a day `delta_days` from the speaker's today.

    Correct agents (and nl2time's describe) say "yesterday at 10:05 PM" or
    "last Saturday", not always an explicit date — day-identification checks
    must accept those, anchored to the scenario's pinned now.
    """
    name = WEEKDAYS[weekday]
    if delta_days == 0:
        return [r"\btoday\b", r"\btonight\b", r"\bthis (?:morning|afternoon|evening)\b"]
    if delta_days == -1:
        return [r"\byesterday\b", r"\blast night\b", rf"\b{name}\b"]
    if delta_days == 1:
        return [r"\btomorrow\b", rf"\b{name}\b"]
    if -7 <= delta_days <= -2:
        return [rf"\b(?:last|this past|on)\s+{name}\b", rf"\b{name}\b"]
    if 2 <= delta_days <= 7:
        return [rf"\b(?:this|this coming|next|on)\s+{name}\b", rf"\b{name}\b"]
    return []


def _day_reference_patterns(local: datetime, now_local: datetime) -> list[str]:
    """Everything that correctly identifies `local`'s civil day: explicit or deictic."""
    delta = (local.date() - now_local.date()).days
    return _day_patterns(local) + _deictic_patterns(delta, local.weekday())


def _strict_day_rejects(utc_view: datetime, now_local: datetime, local: datetime) -> list[str]:
    """Reject renderings of the WRONG (UTC) day, conservatively: explicit date
    forms always; deictic words (today/yesterday/tomorrow/tonight) at delta
    0/±1; qualified weekday forms only when the weekday actually differs from
    the correct day's. Bare weekday names are never rejected (ambiguous)."""
    patterns = _strict_day_patterns(utc_view)
    delta = (utc_view.date() - now_local.date()).days
    if delta == 0:
        patterns += [r"\btoday\b", r"\btonight\b"]
    elif delta == -1:
        patterns += [r"\byesterday\b"]
    elif delta == 1:
        patterns += [r"\btomorrow\b"]
    elif utc_view.weekday() != local.weekday() and 2 <= abs(delta) <= 7:
        name = WEEKDAYS[utc_view.weekday()]
        patterns += [rf"\b(?:last|this past|this coming|next|on)\s+{name}\b"]
    return patterns


def _clock_patterns(local: datetime) -> list[str]:
    h24, minute = local.hour, local.minute
    h12 = h24 % 12 or 12
    ampm = "a" if h24 < 12 else "p"
    pats = [
        rf"\b{h12}:{minute:02d}\s*{ampm}\.?m\b",
        rf"\b{h24:02d}:{minute:02d}\b",
        rf"\b{h24}:{minute:02d}\b",
    ]
    if minute == 0:
        pats.append(rf"\b{h12}\s*{ampm}\.?m\b")
        pats.append(rf"\b{h12}\s+o'?clock\b")
    return pats


def _any(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        if re.search(p, text):
            return p
    return None


def grade_response_check(check: dict[str, Any], text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    kind = check["kind"]
    result: dict[str, Any] = {"kind": kind, "note": check.get("note")}

    if kind == "regex":
        ok = True
        if "accept" in check:
            ok = re.search(check["accept"], text) is not None
            result["accept_matched"] = ok
        if ok and "reject" in check:
            hit = re.search(check["reject"], text)
            if hit:
                ok = False
                result["reject_hit"] = hit.group(0)
        result["passed"] = ok
        return result

    if kind == "count":
        n = check["expected"]
        forms = [str(n)] + ([NUMBER_WORDS[n]] if n < len(NUMBER_WORDS) else [])
        if n == 1:
            forms.append("once")
        elif n == 2:
            forms.append("twice")
        num = rf"\b(?:{'|'.join(forms)})\b"
        unit = check.get("unit")
        if unit:
            pat = rf"(?:{num}[^.!?\n]{{0,50}}?\b(?:{unit})\b|\b(?:{unit})\b[^.!?\n]{{0,30}}?{num})"
        else:
            pat = num
        passed = re.search(pat, text) is not None
        # Enumerations ("* PM-511 … * PM-509 …") are correct answers without a
        # stated total: when the scenario declares an itemRegex, the right
        # number of item mentions also passes.
        item_regex = check.get("itemRegex")
        if not passed and item_regex:
            unique_items = set(re.findall(item_regex, text))
            passed = len(unique_items) == n
            result["item_matches"] = len(unique_items)
        result["passed"] = passed
        return result

    local = _local(check["instant"], check["tz"])
    utc = parse_instant(check["instant"])  # aware UTC
    now_local = _local(context["now"], check["tz"]) if context else local

    if kind == "civilDay":
        hit = _any(_day_reference_patterns(local, now_local), text)
        result["passed"] = hit is not None
        result["accept_hit"] = hit
        if result["passed"] and check.get("rejectUtcDay") and utc.date() != local.date():
            bad = _any(_strict_day_rejects(utc, now_local, local), text)
            if bad:
                result["passed"] = False
                result["reject_hit"] = bad
        return result

    if kind == "clockTime":
        # Only enforced when the response mentions a clock time at all.
        mentions_clock = re.search(r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*[ap]\.?m\b", text) is not None
        if not mentions_clock:
            result["passed"] = True
            result["skipped"] = "no clock time in response"
            return result
        hit = _any(_clock_patterns(local), text)
        result["passed"] = hit is not None
        result["accept_hit"] = hit
        if result["passed"] and check.get("rejectUtcClock") and (utc.hour, utc.minute) != (local.hour, local.minute):
            bad = _any(_clock_patterns(utc), text)
            if bad:
                result["passed"] = False
                result["reject_hit"] = bad
        return result

    if kind == "weekday":
        # Any correct identification of the day satisfies this: the weekday
        # name, an explicit date, or a correct deictic ("yesterday").
        patterns = [rf"\b{WEEKDAYS[local.weekday()]}\b"] + _day_reference_patterns(local, now_local)
        result["passed"] = _any(patterns, text) is not None
        return result

    raise ValueError(f"unknown check kind {kind}")


# ------------------------------------------------------------------- scenario

def grade_scenario(
    scenario_expect: dict[str, Any],
    calls: list[dict[str, Any]],
    response: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = normalize(response)
    tool_results = [grade_tool_call(e, calls) for e in scenario_expect.get("toolCalls", [])]
    check_results = [
        grade_response_check(c, text, context)
        for c in scenario_expect.get("response", {}).get("checks", [])
    ]
    return {
        "nl2time_pass": all(r["passed"] for r in tool_results) if tool_results else None,
        "time2nl_pass": all(r["passed"] for r in check_results) if check_results else None,
        "tool_results": tool_results,
        "check_results": check_results,
    }
