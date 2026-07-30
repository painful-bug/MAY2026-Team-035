"""Status vocabulary mapping.

The frontend puts these exact strings in a `<select>`, so a wrong mapping is a
silently broken dropdown rather than an error.

The stored side has a harder constraint: it must be a member of the baseline's
`public.complaint_status` enum. A value outside that set is a `22P02` from
Postgres, not a bad row -- so `test_every_stored_status_is_a_baseline_enum_member`
is the test that actually protects `PATCH /complaints/{id}`.
"""

from __future__ import annotations

import pytest

from app.domain.vocabularies import (
    status_to_storage,
)

# public.complaint_status, as created by 0001_baseline.sql:14.
BASELINE_COMPLAINT_STATUS = {
    "open",
    "acknowledged",
    "in_progress",
    "resolved",
    "closed",
    "cancelled",
}


@pytest.mark.parametrize(
    ("wire", "expected"),
    [
        ("Pending", "open"),
        ("In Progress", "in_progress"),
        ("in progress", "in_progress"),
        ("RESOLVED", "resolved"),
        ("  Pending  ", "open"),
        ("Cancelled", "cancelled"),
        # The frontend's reopen sets 'Pending'; both land on the same stored
        # value, because the baseline has no separate reopened state. The reopen
        # is recorded as a timeline event instead (0020).
        ("Reopened", "open"),
    ],
)
def test_status_to_storage(wire, expected):
    assert status_to_storage(wire) == expected


@pytest.mark.parametrize(
    "wire",
    ["Pending", "In Progress", "Resolved", "Closed", "Reopened", "Cancelled"],
)
def test_every_stored_status_is_a_baseline_enum_member(wire):
    """Guards the bug this mapping used to have.

    It mapped Pending -> 'pending' and Reopened -> 'reopened', neither of which
    is in the enum, so every such write would have failed against a real
    database.
    """
    assert status_to_storage(wire) in BASELINE_COMPLAINT_STATUS


def test_unknown_status_is_rejected_not_guessed():
    """An unknown status must surface as an error, not become 'open'."""
    assert status_to_storage("Escalated") is None
    assert status_to_storage("") is None
    assert status_to_storage(None) is None
