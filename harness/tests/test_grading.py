from atb.grading import grade_response_check, grade_scenario, grade_tool_call, normalize


EXPECTATION = {
    "tool": "search_transactions",
    "graded": ["start_utc", "end_utc"],
    "argKinds": {"start_utc": "instant-start", "end_utc": "instant-end"},
    "admissible": [
        {"start_utc": "2026-07-19T04:00:00Z", "end_utc": "2026-07-26T04:00:00Z"},
        {"start_utc": "2026-07-20T04:00:00Z", "end_utc": "2026-07-27T04:00:00Z"},
    ],
}


def call(start, end):
    return [{"tool": "search_transactions", "args": {"query": "x", "start_utc": start, "end_utc": end}}]


def test_exact_match_passes():
    assert grade_tool_call(EXPECTATION, call("2026-07-19T04:00:00Z", "2026-07-26T04:00:00Z"))["passed"]


def test_offset_equivalence():
    assert grade_tool_call(EXPECTATION, call("2026-07-19T00:00:00-04:00", "2026-07-26T00:00:00-04:00"))["passed"]


def test_inclusive_end_tolerance():
    assert grade_tool_call(EXPECTATION, call("2026-07-19T04:00:00Z", "2026-07-26T03:59:59Z"))["passed"]


def test_second_tuple_matches():
    assert grade_tool_call(EXPECTATION, call("2026-07-20T04:00:00Z", "2026-07-27T04:00:00Z"))["passed"]


def test_mixed_tuples_fail():
    assert not grade_tool_call(EXPECTATION, call("2026-07-19T04:00:00Z", "2026-07-27T04:00:00Z"))["passed"]


def test_utc_naive_day_bounds_fail():
    assert not grade_tool_call(EXPECTATION, call("2026-07-19T00:00:00Z", "2026-07-26T00:00:00Z"))["passed"]


def test_missing_offset_fails():
    assert not grade_tool_call(EXPECTATION, call("2026-07-19T04:00:00", "2026-07-26T04:00:00Z"))["passed"]


def test_no_call_fails():
    result = grade_tool_call(EXPECTATION, [])
    assert not result["passed"] and not result["called"]


# --------------------------------------------------------------- civil day

JUNE30 = {"kind": "civilDay", "instant": "2026-07-01T02:05:00Z", "tz": "America/New_York", "rejectUtcDay": True}


def test_civil_day_accepts_local():
    for text in ["you paid on june 30.", "paid rent on the 30th of june", "on 6/30/2026", "2026-06-30"]:
        assert grade_response_check(JUNE30, normalize(text))["passed"], text


def test_civil_day_rejects_utc_day():
    assert not grade_response_check(JUNE30, normalize("You last paid rent on July 1."))["passed"]


def test_civil_day_needs_mention():
    assert not grade_response_check(JUNE30, normalize("You paid rent recently."))["passed"]


def test_day_pattern_no_prefix_collision():
    check = {"kind": "civilDay", "instant": "2026-07-01T12:00:00Z", "tz": "UTC"}
    assert not grade_response_check(check, normalize("it happened on july 10"))["passed"]


# --------------------------------------------------------------- clock time

CLOCK = {"kind": "clockTime", "instant": "2026-07-01T02:05:00Z", "tz": "America/New_York", "rejectUtcClock": True}


def test_clock_accepts_local_variants():
    for text in ["at 10:05 pm", "at 10:05pm on june 30", "at 22:05"]:
        assert grade_response_check(CLOCK, normalize(text))["passed"], text


def test_clock_rejects_utc_clock():
    assert not grade_response_check(CLOCK, normalize("rent was paid at 2:05 am"))["passed"]


def test_clock_skipped_when_no_time_mentioned():
    result = grade_response_check(CLOCK, normalize("you paid on june 30"))
    assert result["passed"] and result.get("skipped")


# ------------------------------------------------------------------- count

def test_count_with_unit():
    check = {"kind": "count", "expected": 4, "unit": "times?|purchases?"}
    assert grade_response_check(check, normalize("You bought Starbucks 4 times last week."))["passed"]
    assert grade_response_check(check, normalize("You made four purchases."))["passed"]
    assert not grade_response_check(check, normalize("You bought Starbucks 5 times."))["passed"]


def test_count_not_fooled_by_amounts():
    check = {"kind": "count", "expected": 4, "unit": "times?"}
    assert not grade_response_check(check, normalize("You spent $6.45 at Starbucks 5 times."))["passed"]


# ---------------------------------------------------------------- scenario

def test_grade_scenario_directions():
    expect = {
        "toolCalls": [EXPECTATION],
        "response": {"checks": [{"kind": "count", "expected": 4, "unit": "times?"}]},
    }
    graded = grade_scenario(expect, call("2026-07-19T04:00:00Z", "2026-07-26T04:00:00Z"), "4 times")
    assert graded["nl2time_pass"] and graded["time2nl_pass"]


# ------------------------------------------------------------------- window

WINDOW_EXP = {
    "tool": "query_sleep",
    "graded": ["start_time", "end_time"],
    "admissibleWindow": {
        "startParam": "start_time",
        "endParam": "end_time",
        "core": ["2026-07-22T01:00:00Z", "2026-07-22T11:00:00Z"],
        "envelope": ["2026-07-21T16:00:00Z", "2026-07-22T16:00:00Z"],
    },
}


def wcall(start, end):
    return [{"tool": "query_sleep", "args": {"start_time": start, "end_time": end}}]


def test_window_family_passes():
    for start, end in [
        ("2026-07-22T00:00:00Z", "2026-07-22T14:00:00Z"),   # civil wake day
        ("2026-07-21T16:00:00Z", "2026-07-22T16:00:00Z"),   # full envelope
        ("2026-07-22T01:00:00Z", "2026-07-22T11:00:00Z"),   # exact core
    ]:
        assert grade_tool_call(WINDOW_EXP, wcall(start, end))["passed"], (start, end)


def test_window_missing_core_fails():
    assert not grade_tool_call(WINDOW_EXP, wcall("2026-07-22T02:00:00Z", "2026-07-22T11:00:00Z"))["passed"]


def test_window_exceeding_envelope_fails():
    assert not grade_tool_call(WINDOW_EXP, wcall("2026-07-20T00:00:00Z", "2026-07-22T16:00:00Z"))["passed"]
