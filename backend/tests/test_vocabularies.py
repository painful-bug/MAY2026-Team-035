"""Status and urgency vocabulary mapping.

The frontend puts these exact strings in a `<select>`, so a wrong mapping is a
silently broken dropdown rather than an error.
"""

from __future__ import annotations

import pytest

from app.domain.vocabularies import (
    status_to_storage,
)


@pytest.mark.parametrize(
    ("wire", "expected"),
    [
        ("Pending", "pending"),
        ("In Progress", "in_progress"),
        ("in progress", "in_progress"),
        ("RESOLVED", "resolved"),
        ("  Pending  ", "pending"),
    ],
)
def test_status_to_storage(wire, expected):
    assert status_to_storage(wire) == expected


def test_unknown_status_is_rejected_not_guessed():
    """An unknown status must surface as an error, not become 'pending'."""
    assert status_to_storage("Cancelled") is None
    assert status_to_storage("") is None
    assert status_to_storage(None) is None


