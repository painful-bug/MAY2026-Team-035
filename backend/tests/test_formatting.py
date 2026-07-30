"""Server-side display formatting.

These strings are rendered verbatim by a frontend we cannot change, so the exact
output is a contract, not an implementation detail. The expected values are taken
from frontend/src/data/complaints.js and notices.js.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.formatting import (
    long_date,
    parse_instant,
    time_ago,
)

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=5), "Just now"),
        (timedelta(seconds=59), "Just now"),
        (timedelta(minutes=5), "5m ago"),
        (timedelta(hours=2), "2h ago"),      # complaints.js c1
        (timedelta(hours=4), "4h ago"),      # complaints.js c3
        (timedelta(days=1), "1d ago"),       # complaints.js c2
        (timedelta(days=2), "2d ago"),       # complaints.js c4
        (timedelta(days=9), "1w ago"),
        (timedelta(days=60), "2mo ago"),
    ],
)
def test_time_ago_matches_the_frontend_vocabulary(delta, expected):
    assert time_ago(NOW - delta, now=NOW) == expected


def test_time_ago_never_renders_a_negative():
    """Clock skew must not produce '-3h ago' in front of a resident."""
    assert time_ago(NOW + timedelta(hours=3), now=NOW) == "Just now"


def test_long_date_matches_the_notices_format():
    assert long_date(NOW) == "July 8, 2026"


def test_long_date_has_no_zero_padded_day():
    """'July 8, 2026', never 'July 08, 2026' -- %-d is unavailable on Windows."""
    assert long_date(datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)) == "July 3, 2026"


def test_parse_instant_accepts_both_postgrest_shapes():
    assert parse_instant("2026-07-08T12:00:00+00:00") == NOW
    assert parse_instant("2026-07-08T12:00:00Z") == NOW
    assert parse_instant(NOW) == NOW


def test_naive_datetimes_are_treated_as_utc():
    assert time_ago(datetime(2026, 7, 8, 10, 0), now=NOW) == "2h ago"
