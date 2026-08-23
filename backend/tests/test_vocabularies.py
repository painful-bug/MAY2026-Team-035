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
    booking_status_to_storage,
    booking_status_to_wire,
    comment_visibility_to_storage,
    complaint_status_filter,
    complaint_status_to_wire,
    status_to_storage,
)

# public.booking_status, as created by 0001_baseline.sql:16.
BASELINE_BOOKING_STATUS = {
    "requested",
    "approved",
    "rejected",
    "cancelled",
    "completed",
    "no_show",
}

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


# ---------------------------------------------------------------------------
# The filter direction
#
# `status_to_storage` answers "what do I store when the user picks this", which
# is the right question when writing and the wrong one when filtering a list.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wire", "expected"),
    [
        ("Pending", ["open"]),
        # Two stored statuses render as one word. A filter carrying only one of
        # them returns a list missing rows that same list displays under the
        # word the caller typed.
        ("In Progress", ["acknowledged", "in_progress"]),
        ("Resolved", ["closed", "resolved"]),
        ("Cancelled", ["cancelled"]),
    ],
)
def test_a_filter_matches_every_status_that_renders_as_the_word_asked_for(
    wire, expected
):
    assert sorted(complaint_status_filter(wire)) == expected


def test_an_unrenderable_word_is_rejected_rather_than_matching_nothing():
    """`Closed` is a stored value, not something this surface ever shows -- so a
    caller asking for it is a caller guessing. An empty match list would look
    like "you have none of those"."""
    assert complaint_status_filter("Closed") is None
    assert complaint_status_filter("Escalated") is None
    assert complaint_status_filter("") is None
    assert complaint_status_filter(None) is None


def test_every_word_this_surface_renders_can_be_filtered_by():
    """The two directions are derived from one map, so this cannot drift -- which
    is the point of asserting it rather than trusting it.
    """
    for stored in BASELINE_COMPLAINT_STATUS:
        shown = complaint_status_to_wire(stored)
        assert stored in complaint_status_filter(shown)


# ---------------------------------------------------------------------------
# Comment visibility
#
# The same shape of bug as the statuses above, and it had the same cause: the
# request was forwarded to the database unmapped. `complaint_comments` allows
# only `public` and `internal` (0020:101); the frontend, API.md and the schema
# default all say `resident`. Every comment posted through
# `POST /complaints/{id}/comments` was therefore a 23514 -> 422.
# ---------------------------------------------------------------------------

# complaint_comments_visibility_check, as created by 0020:101.
STORED_COMMENT_VISIBILITY = {"public", "internal"}


@pytest.mark.parametrize(
    ("wire", "expected"),
    [
        # What the frontend actually sends -- createComplaintsSlice.js:182.
        ("resident", "public"),
        ("internal", "internal"),
        # Accepted too, so a client that has already learnt the stored word is
        # not forced back through the display word to talk to us.
        ("public", "public"),
        ("  Resident  ", "public"),
        ("INTERNAL", "internal"),
    ],
)
def test_comment_visibility_to_storage(wire, expected):
    assert comment_visibility_to_storage(wire) == expected


@pytest.mark.parametrize("wire", ["resident", "public", "internal"])
def test_every_stored_visibility_satisfies_the_check_constraint(wire):
    """The test that actually protects `POST /complaints/{id}/comments`.

    Its sibling above would still pass if the map returned `resident` for
    `resident`, which is exactly the bug that shipped.
    """
    assert comment_visibility_to_storage(wire) in STORED_COMMENT_VISIBILITY


def test_an_unknown_visibility_is_rejected_rather_than_defaulted():
    """Not symmetrical with the other unknowns in this module, and deliberately
    so: guessing `public` here would publish to the resident a comment somebody
    may have meant to keep internal."""
    assert comment_visibility_to_storage("private") is None
    assert comment_visibility_to_storage("admins") is None
    assert comment_visibility_to_storage("") is None
    assert comment_visibility_to_storage(None) is None


# ---------------------------------------------------------------------------
# Booking status -- three spellings of one fact
#
# `amenity_bookings.status` is the enum ('requested'); the overview views also
# expose it initcap'd for display ('Pending', 'No Show'); and the app's own word
# for that first state is 'pending', which is what `bookingStatuses.js` and
# `_APPROVAL_FILTERS` are built on. One wire word per state, or every
# case-sensitive comparison downstream is a coin flip (issue #48 D4).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # The stored enum.
        ("requested", "pending"),
        ("approved", "approved"),
        ("no_show", "no_show"),
        # The views' display spelling, including the two-word one.
        ("Pending", "pending"),
        ("Approved", "approved"),
        ("No Show", "no_show"),
        # Already normalised, and the hyphenated spelling a client might send.
        ("pending", "pending"),
        ("no-show", "no_show"),
        ("  APPROVED  ", "approved"),
        # Absent is pending: an unsaved booking has been asked for, not decided.
        (None, "pending"),
        ("", "pending"),
    ],
)
def test_booking_status_to_wire(value, expected):
    assert booking_status_to_wire(value) == expected


def test_the_wire_never_carries_the_enums_name_for_the_pending_state():
    """The test that actually protects the comparison.

    Its sibling above would still pass if the map returned 'requested' for
    'requested' -- which is precisely what the first fix for this defect did,
    because the stored value looked like it was already a machine value.
    """
    assert "requested" not in {
        booking_status_to_wire(stored) for stored in BASELINE_BOOKING_STATUS
    }


@pytest.mark.parametrize("stored", sorted(BASELINE_BOOKING_STATUS))
def test_every_stored_status_survives_a_round_trip(stored):
    """Wire and back. A filter that cannot make this trip matches no rows."""
    assert booking_status_to_storage(booking_status_to_wire(stored)) == stored


@pytest.mark.parametrize("wire", ["pending", "approved", "cancelled", "No Show"])
def test_every_wire_status_maps_onto_a_baseline_enum_member(wire):
    """`amenity_ledger_overview.booking_status` is the raw enum, so a filter
    value outside this set is a filter that silently matches nothing."""
    assert booking_status_to_storage(wire) in BASELINE_BOOKING_STATUS


def test_an_unknown_booking_status_is_rejected_rather_than_defaulted():
    """A filter is the one place guessing is worse than refusing: defaulting an
    unrecognised status to 'pending' would answer a question nobody asked."""
    assert booking_status_to_storage("confirmed") is None
    assert booking_status_to_storage("blocked") is None
    assert booking_status_to_storage("") is None
    assert booking_status_to_storage(None) is None
