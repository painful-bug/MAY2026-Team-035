"""The notice board, the flat, and the numbers a resident should be able to ring.

Three small surfaces with one thing in common: every one of them is currently
either unserved or, in the directory's case, **hard-coded in a JSX file**. §5.6
is about the second, and the argument generalises — a contact list maintained by
editing a component is stale the day it ships.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app.domain.common_schemas import CamelModel


def _optional_text(limit: int) -> object:
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=limit)]


class Notice(CamelModel):
    """One published notice.

    ``urgency`` is title-cased on the wire — `Info`, `Important`, `Urgent` —
    because that is what `Notices.jsx` renders, while the CHECK in `0018` stores
    lower case. Same two-vocabulary treatment as complaints and visitor passes,
    in the same place: the view.

    **Drafts never appear here.** A notice with no `publishedAt` is one an admin
    is still writing, and the resident view excludes it as well as the policy —
    two independent reasons a resident cannot read one.
    """

    id: str
    title: str
    body: str
    category: str = "General"
    #: `Info` | `Important` | `Urgent`.
    urgency: str = "Info"
    published_at: datetime
    author_name: str | None = None


class HouseholdMember(CamelModel):
    """Somebody or something registered to the caller's flat.

    ``source`` is the field that stops a caller guessing. `member` is a person
    with an account, a membership and a role; `contact` is a phone number a
    resident added so the gate and the office have it, which grants nothing and
    belongs to nobody who can log in.

    Collapsing the two would be the prototype's mistake: `createUsersSlice.js`
    manufactures a whole user row for a phone number, and a system that did that
    for real would put someone in the member count who cannot sign in and never
    agreed to join.
    """

    id: str
    #: `member` | `contact`.
    source: str
    full_name: str
    phone_e164: str | None = None
    #: `Owner`, `Tenant`, `Family Member` … for a member; free text for a contact.
    relationship: str = ""
    is_primary_contact: bool = False
    #: `Active` | `Pending` | `Suspended` | `Ended` for a member; `Contact` for a
    #: number. The screen renders this as a badge and has always had one.
    status: str
    since: datetime | None = None


class AddHouseholdPhoneRequest(CamelModel):
    """A number to register against the caller's own flat.

    **The flat is not in this body.** It is resolved from the caller's residency
    inside the RPC, because a unit id in a request is a unit id somebody can
    change — and the whole point of this endpoint is that a resident may edit
    their own flat's list without an admin.

    Idempotent on the number: adding the same one twice updates the name rather
    than failing, since a correction is the likeliest reason anybody repeats it.
    """

    phone_e164: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=4, max_length=20)
    ]
    full_name: _optional_text(120) = ""  # type: ignore[valid-type]
    relationship: _optional_text(60) = ""  # type: ignore[valid-type]


class ManagementContact(CamelModel):
    """One entry in the contact directory.

    Served from `departments` (§5.6) rather than a table of its own, so it stays
    current as a side effect of admin work that already happens. `US-2.9` asks
    for a directory somebody can trust, and the failure mode it names is a list
    nobody remembers to update.

    ``category`` is the free text an admin typed on the department — `Security`,
    `Maintenance`, `Management`. **There is no emergency flag**, deliberately:
    deciding which categories mean *emergency* by matching strings in SQL would
    be a classification invented here and wrong the first time somebody writes
    "Emergencies". If the product wants that distinction it is one boolean on a
    table the admin workstream owns.
    """

    id: str
    name: str
    category: str = "Management"
    description: str = ""
    phone_e164: str | None = None
    email: str | None = None
    #: The department's staffed window, when it keeps one.
    opens_at: str | None = None
    closes_at: str | None = None
    head_name: str | None = None
    head_phone_e164: str | None = None
