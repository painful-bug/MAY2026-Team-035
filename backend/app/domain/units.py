"""Flat-code normalisation.

The frontend represents a flat two incompatible ways and the backend has to
accept both, because we cannot change it.

**The inconsistency is a live frontend bug, not just a style difference.**
``createPendingRequestsSlice.js`` builds the flat code as
``` `${request.tower}-${request.flat}` ```. That is correct when the request came
from the registration form, where ``flat`` holds a bare number (``505``), giving
``C-505``. But the seeded requests in ``data/pendingRequests.js`` already store
``flat: 'C-505'`` -- so approving a seeded request produces **``C-C-505``**, a
flat that does not exist and never will.

:func:`normalize_unit_code` accepts either shape and yields one canonical code.
Raised with the frontend team as agenda item 8.
"""

from __future__ import annotations

import re

# A bare flat number as the registration form collects it: digits, optionally
# with a letter suffix ('505', '1204', '12B'). Anything else is treated as an
# already-complete label and left alone.
_BARE_NUMBER = re.compile(r"^\d{1,5}[A-Za-z]?$")


def normalize_unit_code(tower: str | None, flat: str | None) -> str | None:
    """Return the canonical flat code for a ``(tower, flat)`` pair.

    >>> normalize_unit_code("C", "505")
    'C-505'
    >>> normalize_unit_code("C", "C-505")      # already qualified -- not doubled
    'C-505'
    >>> normalize_unit_code("B", "Admin Office")  # not a flat at all
    'Admin Office'
    >>> normalize_unit_code(None, "A-102")
    'A-102'
    """
    flat = (flat or "").strip()
    tower = (tower or "").strip()

    if not flat:
        return None
    if not tower:
        return flat

    # Already prefixed with this tower -- the seeded-request case. Case-insensitive
    # because nothing guarantees the two fields agree on capitalisation.
    if flat.upper().startswith(f"{tower.upper()}-"):
        return flat

    # A bare number gets the tower prefix; anything else ('Admin Office', or a
    # code qualified by a *different* tower) is taken as authoritative, because
    # guessing would corrupt it.
    if _BARE_NUMBER.match(flat):
        return f"{tower}-{flat}"
    return flat
