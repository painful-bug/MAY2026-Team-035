"""Display formatting the server is forced to do on the frontend's behalf.

The React app renders ``complaints[].timeAgo`` ("2h ago") and ``notices[].date``
("July 8, 2026") directly, with no client-side formatting step. We cannot change
``frontend/src/``, so the server produces those strings.

**This has a cost, and it is deliberate rather than accidental.** A response
containing a relative time is only correct at the instant it is generated, so it
can never be cached -- every endpoint that emits ``timeAgo`` must send
``Cache-Control: no-store``. It also puts the server's clock and timezone into a
value that properly belongs to the browser.

Every DTO therefore carries BOTH the formatted string and the raw ISO-8601
instant beside it (``timeAgo`` + ``submittedAt``, ``date`` + ``publishedAt``), so
the frontend can move to client-side formatting one screen at a time and we can
drop ``no-store`` per endpoint as it does. See docs/FRONTEND_MEETING_AGENDA.md
item 3.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# A5: the community's timezone is not stored anywhere -- not in `communities`,
# not in the ERD. Assumed IST, which the product's currency, phone format and
# names all point to. It is wrong for any community outside India, so when
# `communities.timezone` exists this constant becomes a per-community lookup.
# Isolated here so that change is one function's worth of work.
#
# A FIXED OFFSET, not ZoneInfo("Asia/Kolkata"), for a reason found by running it:
# on Windows the stdlib `zoneinfo` has no timezone database of its own and raises
# ZoneInfoNotFoundError unless the `tzdata` package is installed -- at import
# time, so the whole app fails to start. A fixed offset is not a workaround here,
# it is exactly correct: India has never observed daylight saving, so UTC+05:30
# holds year-round. Supporting communities in a DST-observing zone would need
# real zone data, and `tzdata` becomes a dependency at that point.
COMMUNITY_TZ = timezone(timedelta(hours=5, minutes=30), name="IST")

_MINUTE = 60
_HOUR = 60 * _MINUTE
_DAY = 24 * _HOUR
_WEEK = 7 * _DAY


def parse_instant(value: str | datetime) -> datetime:
    """Parse a PostgREST ``timestamptz`` string into an aware datetime.

    PostgREST normally emits ``+00:00`` but can emit a bare ``Z``, which
    ``fromisoformat`` rejects before Python 3.11. Normalised here so the service
    runs on 3.10, the version in ``backend/.venv``.
    """
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _as_utc(instant: datetime) -> datetime:
    """Treat a naive datetime as UTC; leave aware ones alone.

    Postgres ``timestamptz`` always round-trips as aware, but a caller passing a
    naive value should not silently get a local-time answer.
    """
    if instant.tzinfo is None:
        return instant.replace(tzinfo=timezone.utc)
    return instant


def time_ago(instant: datetime, *, now: datetime | None = None) -> str:
    """Format ``instant`` the way the complaints list renders it ("2h ago").

    Mirrors the vocabulary already present in ``frontend/src/data/complaints.js``:
    ``2h ago``, ``1d ago``, ``2d ago``.
    """
    instant = _as_utc(instant)
    current = _as_utc(now or datetime.now(timezone.utc))
    seconds = int((current - instant).total_seconds())

    # Clock skew, or a due date in the future: never render "-3h ago".
    if seconds < 0:
        return "Just now"
    if seconds < _MINUTE:
        return "Just now"
    if seconds < _HOUR:
        return f"{seconds // _MINUTE}m ago"
    if seconds < _DAY:
        return f"{seconds // _HOUR}h ago"
    if seconds < _WEEK:
        return f"{seconds // _DAY}d ago"
    if seconds < 30 * _DAY:
        return f"{seconds // _WEEK}w ago"
    return f"{seconds // (30 * _DAY)}mo ago"


def clock_time(value: str | None) -> str | None:
    """Normalise a Postgres ``time`` to the ``HH:MM`` an ``<input type="time">`` needs.

    PostgREST renders a ``time`` column as ``08:00:00``; the frontend stores
    ``operatingHours: {start: '08:00'}`` and feeds it straight to a time input,
    which shows an empty field for anything it cannot parse. Truncating here
    rather than in each DTO keeps that knowledge in one place.

    No timezone conversion: a department's opening hour is a wall-clock time in
    the community, not an instant, so there is nothing to convert it *from*.
    """
    if not value:
        return None
    parts = str(value).split(":")
    if len(parts) < 2:
        return None
    return f"{parts[0]:0>2}:{parts[1][:2]}"


def bill_period(start: str | date | None, end: str | date | None) -> str:
    """Format an invoice's billing period the way the payments list renders it.

    ``"July 1, 2026 - July 31, 2026"`` for a period, and ``"One-time charge"``
    when there is none -- both strings taken verbatim from
    ``frontend/src/data/payments.js``, where a clubhouse charge carries the
    second.

    Unlike :func:`time_ago` this is safe to cache: a billing period is fixed at
    issue and never becomes stale.
    """
    first = _as_date(start)
    last = _as_date(end)
    if first is None and last is None:
        return "One-time charge"
    if first is None or last is None:
        only = first or last
        assert only is not None  # narrowed by the checks above
        return _long_day(only)
    if first == last:
        return _long_day(first)
    return f"{_long_day(first)} - {_long_day(last)}"


def _as_date(value: str | date | None) -> date | None:
    """Accept a PostgREST ``date`` string, a real date, or nothing."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _long_day(value: date) -> str:
    """``July 1, 2026``. No timezone shift: a billing period is a calendar range,
    not an instant, so converting it to :data:`COMMUNITY_TZ` would move it."""
    return f"{value:%B} {value.day}, {value.year}"


def long_date(instant: datetime) -> str:
    """Format as ``July 8, 2026`` -- the notices list's ``date`` field.

    Built by hand rather than with ``strftime('%B %-d, %Y')`` because ``%-d`` is a
    glibc extension that raises on Windows, and this project is developed there.
    """
    local = _as_utc(instant).astimezone(COMMUNITY_TZ)
    return f"{local:%B} {local.day}, {local.year}"
