"""Flat-code normalisation.

The cases that matter are the ones that come from the frontend's two
incompatible representations of a flat -- see app/domain/units.py.
"""

from __future__ import annotations

import pytest

from app.domain.units import normalize_unit_code


@pytest.mark.parametrize(
    ("tower", "flat", "expected"),
    [
        # The registration form: a bare number gets the tower prefix.
        ("C", "505", "C-505"),
        ("A", "102", "A-102"),
        ("B", "1204", "B-1204"),
        # The seeded requests: already qualified, and must NOT become 'C-C-505'.
        # This is the live frontend bug this function exists to absorb.
        ("C", "C-505", "C-505"),
        ("a", "A-102", "A-102"),  # capitalisation need not agree
        # Not a flat at all -- admins use this literal value.
        ("B", "Admin Office", "Admin Office"),
        # Qualified by a different tower: taken as authoritative, because
        # guessing which field is right would corrupt one of them.
        ("B", "C-505", "C-505"),
        # Missing pieces.
        (None, "A-102", "A-102"),
        ("", "A-102", "A-102"),
        ("C", "", None),
        ("C", None, None),
        # A letter suffix is still a bare flat number.
        ("D", "12B", "D-12B"),
    ],
)
def test_normalize_unit_code(tower, flat, expected):
    assert normalize_unit_code(tower, flat) == expected


def test_normalisation_is_idempotent():
    """Applying it twice must not double the prefix -- the bug's exact shape."""
    once = normalize_unit_code("C", "505")
    assert normalize_unit_code("C", once) == once
