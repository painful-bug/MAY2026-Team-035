"""Status and urgency vocabulary mapping.

The frontend puts these exact strings in a `<select>`, so a wrong mapping is a
silently broken dropdown rather than an error.
"""

from __future__ import annotations

import pytest

from app.domain.vocabularies import (
    is_open,
    status_to_storage,
    status_to_wire,
    urgency_to_storage,
    urgency_to_wire,
)


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        # Deliberately not round-trips -- the frontend's select has three options.
        ("closed", "Resolved"),
        ("reopened", "Pending"),
    ],
)
def test_status_to_wire(stored, expected):
    assert status_to_wire(stored) == expected


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


def test_status_to_wire_falls_back_safely():
    """A stored value we do not recognise still renders something valid."""
    assert status_to_wire("something_new") == "Pending"
    assert status_to_wire(None) == "Pending"


def test_wire_mapping_is_stable_under_round_trip():
    """to_wire(to_storage(x)) == x for every value the frontend can send."""
    for wire in ("Pending", "In Progress", "Resolved"):
        assert status_to_wire(status_to_storage(wire)) == wire


@pytest.mark.parametrize(
    ("stored", "expected"),
    [("low", "Low"), ("medium", "Medium"), ("high", "High")],
)
def test_urgency_to_wire(stored, expected):
    assert urgency_to_wire(stored) == expected


def test_urgency_to_storage():
    assert urgency_to_storage("High") == "high"
    assert urgency_to_storage("  low ") == "low"
    assert urgency_to_storage("Critical") is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("pending", True),
        ("in_progress", True),
        ("reopened", True),
        ("resolved", False),
        ("closed", False),
        (None, False),
    ],
)
def test_is_open(status, expected):
    assert is_open(status) is expected
