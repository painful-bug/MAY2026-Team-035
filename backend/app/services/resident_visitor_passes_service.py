"""The resident's visitor passes: minting one, following it, settling it.

Closes §3.4 and §5.4 of ``docs/design/RESIDENT_BACKEND_DESIGN.md`` and step 5 of
its build order.

**This module holds the plaintext, and it is the only one that ever does.** The
code and the token are minted here, hashed here, and the hashes alone are sent to
the repository. They appear in exactly one response -- the ``201`` that creates
the pass -- and there is no code path anywhere that can produce them again.

Everything else is translation. The validity window is computed in the database
from the community's setting, the transitions are refused in
``decide_visitor_pass``, and ownership is checked by ``is_own_membership``.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from app.core.exceptions import ConflictError, NotFoundError
from app.core.tokens import hash_secret
from app.domain.common_schemas import Page
from app.domain.resident_visitor_schemas import (
    CreateVisitorPassRequest,
    VisitorPass,
    VisitorPassCreated,
)
from app.domain.vocabularies import visitor_status_to_wire
from app.repositories import resident_visitor_passes_repository as repo
from supabase import Client

#: Six digits, matching what a resident is asked to read down a phone line.
#:
#: That is roughly twenty bits, which is **not** enough to stand alone against an
#: online guessing attack, and saying so is more useful than quietly making the
#: code longer than the product wants it. Three things carry the difference: the
#: code is unique only among *live* passes in one community (`0032`), a pass
#: expires on the community's TTL, and any future gate-verification endpoint must
#: rate-limit by community. The third does not exist yet -- there is no gate
#: software in this repository -- and it is recorded in `API.md` as an
#: obligation on whoever builds it rather than left to be rediscovered. (Those
#: are `API.md` §13 and §15; the meta-sections shifted when §14 was added.)
_CODE_LOW = 100_000
_CODE_HIGH = 999_999

#: How many times a rejected code is redrawn before the caller is told.
#:
#: `0032` puts a unique index on `(community_id, code_hash)` over live passes, so
#: two residents in one community can be handed the same six digits and the
#: second insert is refused. That refusal is correct and it is not the resident's
#: problem: nothing about their request was wrong, and *"could not create the
#: visitor pass"* is an answer they cannot act on.
#:
#: This is also the only place a retry can happen. The database cannot resolve
#: the collision itself -- it holds a hash and no way back to a code -- so
#: re-minting belongs wherever the plaintext is, which by design is here and
#: nowhere else.
#:
#: Five, because the odds compound. Against a community holding a thousand live
#: passes at once -- far past anything realistic -- one draw collides about once
#: in nine hundred, and five in a row is a number with no practical meaning. What
#: five buys is the guarantee that this terminates: an unbounded loop against a
#: full code space is an outage rather than a retry.
_CODE_ATTEMPTS = 5


def _mint_security_code() -> str:
    """A six-digit code from the CSPRNG.

    ``secrets`` rather than ``random``: the module difference is the whole
    security property, and a gate credential drawn from a Mersenne twister is
    predictable to anyone who has seen a few of them.
    """
    return str(secrets.randbelow(_CODE_HIGH - _CODE_LOW + 1) + _CODE_LOW)


def _derive_visitor_name(purpose: str, purpose_details: str) -> str:
    """The label the prototype builds when nobody typed a name.

    The resident's pre-approval form collects a purpose, a guest count, a date
    and a time -- and **no visitor name**. ``createVisitorsSlice.js`` composes
    one: the purpose followed by ``group``, using the free text when the purpose
    is ``Other`` and the selected option otherwise.

    ``visitor_requests.visitor_name`` is ``not null``, and the string a gate
    reads in its notification is that column, so something has to produce it.
    Requiring it of the client would mean requiring a field their form does not
    have; deriving it here keeps one rule in one place, and it is the product's
    rule rather than a rendering choice, because it outlives the screen in a
    notification and an event log.
    """
    label = (purpose_details or "").strip() if purpose == "Other" else purpose
    return f"{(label or purpose or 'Visitor').strip()} group"


def _text(value: object) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _pass_fields(row: dict[str, Any]) -> dict[str, Any]:
    """The fields every visitor-pass response carries.

    One function, so the created pass and the same pass read back a second later
    cannot disagree about itself.
    """
    return {
        "id": row["id"],
        "visitor_name": _text(row.get("visitor_name")),
        "purpose": _text(row.get("purpose")) or "Guest",
        "purpose_details": _text(row.get("purpose_details")),
        "guest_count": int(row.get("guest_count") or 1),
        "status": visitor_status_to_wire(row.get("status")),
        "valid_from": row.get("valid_from"),
        "valid_until": row.get("valid_until"),
        "checked_in_at": row.get("checked_in_at"),
        "checked_out_at": row.get("checked_out_at"),
        "decided_at": row.get("decided_at"),
        "cancelled_at": row.get("cancelled_at"),
        "created_at": row["created_at"],
        "is_current": bool(row.get("is_current")),
        "is_lapsed": bool(row.get("is_lapsed")),
    }


def _to_pass(row: dict[str, Any]) -> VisitorPass:
    return VisitorPass(**_pass_fields(row))


def list_mine(
    client: Client,
    *,
    membership_id: str,
    view: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[VisitorPass]:
    """One page of the caller's own passes, newest first.

    ``view`` is ``current`` or ``history``; anything else -- including nothing --
    means both. An unrecognised value is **not** an error here, unlike the
    complaint status filter: `view` is a tab selector with two known values, and
    the honest answer to a third is the unfiltered list rather than a 422 about a
    parameter the client did not mean to constrain.
    """
    wanted = (view or "").strip().casefold()
    current: bool | None = None
    if wanted == "current":
        current = True
    elif wanted == "history":
        current = False

    offset = max(page - 1, 0) * page_size
    rows, total = repo.list_mine(
        client,
        membership_id=membership_id,
        current=current,
        offset=offset,
        limit=page_size,
    )
    items = [_to_pass(row) for row in rows]
    return Page(
        items=items,
        total=total,
        page=max(page, 1),
        page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


def get_mine(client: Client, *, membership_id: str, pass_id: str) -> VisitorPass:
    """One of the caller's passes -- the QR screen's read.

    A pass that exists but belongs to someone else is a 404, identical to one
    that does not exist.
    """
    row = repo.get_mine(client, membership_id=membership_id, pass_id=pass_id)
    if row is None:
        raise NotFoundError("Visitor pass not found.", code="visitor_pass_not_found")
    return _to_pass(row)


def create_pass(
    client: Client, *, membership_id: str, body: CreateVisitorPassRequest
) -> VisitorPassCreated:
    """Pre-approve a visitor, returning the plaintext code exactly once.

    The read-back is what makes the response honest about the parts the resident
    did not choose: ``validUntil`` comes from the community's TTL setting and
    ``status`` from the RPC. Echoing the request back with a code attached would
    return everything except the answers.

    A code the community is already using is redrawn rather than reported; see
    ``_CODE_ATTEMPTS``. The token is minted once outside that loop -- it is 32
    bytes from the CSPRNG, and a collision there would not be a coincidence.
    """
    pass_token = secrets.token_urlsafe(32)
    visitor_name = body.visitor_name or _derive_visitor_name(
        body.purpose, body.purpose_details
    )

    for attempt in range(_CODE_ATTEMPTS):
        security_code = _mint_security_code()
        try:
            pass_id = repo.create_pass(
                client,
                membership_id=membership_id,
                visitor_name=visitor_name,
                purpose=body.purpose,
                purpose_details=body.purpose_details,
                guest_count=body.guest_count,
                expected_at=_isoformat(body.expected_at),
                pass_hash=hash_secret(pass_token),
                code_hash=hash_secret(security_code),
            )
        except ConflictError as exc:
            # Only a duplicate key is worth another draw. Every other conflict is
            # a fact about the request that a new code would not change, and
            # retrying one would just be a slower way to return it.
            if exc.code != "unique_violation" or attempt == _CODE_ATTEMPTS - 1:
                raise
            continue
        break

    row = repo.get_mine(client, membership_id=membership_id, pass_id=pass_id)
    if row is None:  # pragma: no cover - the RPC just created it
        raise NotFoundError("Visitor pass not found.", code="visitor_pass_not_found")

    return VisitorPassCreated(
        **_pass_fields(row),
        security_code=security_code,
        pass_token=pass_token,
    )


def decide(
    client: Client, *, membership_id: str, pass_id: str, decision: str
) -> VisitorPass:
    """Approve, reject or cancel one of the caller's passes.

    The ownership check and every refusal are the RPC's: it holds the row and can
    decline in the same statement that would have changed it. What this does is
    read the result back, so the client renders the state the database settled on
    rather than the one it assumed.
    """
    repo.decide(client, pass_id=pass_id, decision=decision)
    return get_mine(client, membership_id=membership_id, pass_id=pass_id)


def checkout(client: Client, *, membership_id: str, pass_id: str) -> VisitorPass:
    """Return the authoritative pass after the ownership-checked checkout RPC."""
    repo.checkout(client, membership_id=membership_id, pass_id=pass_id)
    return get_mine(client, membership_id=membership_id, pass_id=pass_id)


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
