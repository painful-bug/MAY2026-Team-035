"""The resident's view of a visitor pass.

**The one field that appears in exactly one response.** ``securityCode`` is on
``VisitorPassCreated`` and on nothing else. §5.4: the code admits a stranger
through a gate, so it is stored as a hash and returned once, in the response
that mints it. Putting it on ``VisitorPass`` would make every list read a
credential disclosure — and would be an easy, invisible mistake, which is why the
two are separate models rather than one model with a nullable field.

``passToken`` is the QR payload's handle and follows the same rule for the same
reason: a QR code photographed off a screen is a credential someone else now
holds.

**Vocabulary.** ``status`` is the frontend's word, translated in
``domain/vocabularies.py``. The column says ``denied``; every screen in the
prototype says ``Rejected``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.domain.common_schemas import CamelModel


def _required_text(limit: int) -> object:
    """Required free text, trimmed before it is measured."""
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=limit),
    ]


def _optional_text(limit: int) -> object:
    """Optional free text, trimmed."""
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=limit)]


class VisitorPass(CamelModel):
    """One pass, as every read returns it.

    Carries **neither** the security code nor the pass token — not even hashed.
    ``visitor_pass_overview`` does not select those columns, so this model could
    not carry them by accident.

    ``isCurrent`` is what splits the two tabs: a pass still ahead of the resident
    against one they are finished with. Computed in the view, so the split cannot
    drift from the transitions the RPC allows.
    """

    id: str
    visitor_name: str
    purpose: str
    purpose_details: str = ""
    guest_count: int
    #: ``Expected`` | ``Pending Approval`` | ``Approved`` | ``Rejected`` |
    #: ``Checked In`` | ``Checked Out`` | ``Expired`` | ``Cancelled``.
    status: str
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None
    decided_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    is_current: bool
    #: Still in an open state but past its window — the pass the gate will refuse
    #: while the resident's screen still calls it `Expected`. Surfaced so the
    #: client can say *lapsed* rather than leaving them to work it out from two
    #: timestamps.
    is_lapsed: bool


class VisitorPassCreated(VisitorPass):
    """The response to creating a pass, and the only place the code appears.

    Both secrets are returned **once**. There is no endpoint that will show them
    again, and no support procedure that can recover them — a resident who loses
    the code issues a new pass. That is the correct trade for a gate credential
    and it is how the invite flow already behaves.
    """

    #: The short code the resident reads aloud. Six digits, hashed at rest.
    security_code: str
    #: The handle inside the QR payload.
    pass_token: str


class CreateVisitorPassRequest(CamelModel):
    """What the pre-approval form collects.

    ``expectedAt`` is a single instant rather than the form's separate date and
    time fields. Two fields is a rendering decision; one instant is what a
    validity window is computed from, and combining them in the client is the
    only place the browser's timezone is known.

    ``validUntil`` is **not** accepted. The window is the expected arrival plus
    the community's `visitorCodeTtlMinutes`, applied in the database — a
    resident who could choose it could mint a pass valid for a year. The TTL runs
    from the arrival *or from now, whichever is later*: the form floors the date
    at today but not the time, and a pass whose window closed before it was
    issued is one nobody could use and nothing reported.
    """

    #: **Optional, because the form does not collect it.** The resident's
    #: pre-approval screen asks for a purpose, a date, a time and a guest count
    #: and nothing else; the prototype composes a label from the purpose. Sent
    #: empty, the API composes the same one. Accepted when present because the
    #: gate's own screen does collect a name, and that surface is coming.
    visitor_name: _optional_text(120) = ""  # type: ignore[valid-type]
    #: `Guest` | `Service` | `Other` today, free text in practice: the select's
    #: options are a frontend list and a CHECK here would need a migration every
    #: time somebody added one.
    purpose: _required_text(60)  # type: ignore[valid-type]
    #: What the form collects when `purpose` is `Other`. Kept as its own field so
    #: a typed "Delivery" stays distinguishable from the selected one.
    purpose_details: _optional_text(500) = ""  # type: ignore[valid-type]
    guest_count: int = Field(default=1, ge=1, le=50)
    expected_at: datetime | None = None
