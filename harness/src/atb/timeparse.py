"""Instant parsing/comparison used by both mocks and graders.

An "instant" arg is any ISO-8601 datetime string. Comparison is by absolute
time, so `2026-07-19T04:00:00Z` == `2026-07-19T00:00:00-04:00`. A bare
datetime with no offset (a common model mistake) parses as None here — the
caller decides how to treat it (mocks: tool error; graders: fail).
"""

from __future__ import annotations

from datetime import datetime, timezone

END_TOLERANCE_SECONDS = 1.0


def parse_instant(value: object) -> datetime | None:
    """Parse an ISO-8601 datetime WITH offset (Z or ±hh:mm) to an aware UTC datetime."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def instants_equal(a: datetime, b: datetime) -> bool:
    return abs((a - b).total_seconds()) < 0.0005


def end_matches(actual: datetime, golden_end: datetime) -> bool:
    """Exact half-open end, or the inclusive-end idiom (up to 1s early: 23:59:59[.999])."""
    delta = (golden_end - actual).total_seconds()
    return -0.0005 < delta <= END_TOLERANCE_SECONDS
