"""DTOs for the complaints surfaces.

Request bodies only. The complaints read path is their ``GET /dashboard/snapshot``,
which projects each complaint with its comments and history embedded, so the
response DTOs this module used to carry (summary, detail, timeline, comments,
attachments) went with the reads that were removed -- see
``docs/FRONTEND_WIRING_AUDIT.md`` §3.
"""

from __future__ import annotations

from typing import Annotated, Any

from datetime import datetime

from pydantic import Field, StringConstraints

from app.domain.common_schemas import CamelModel


def _required_text(limit: int) -> object:
    """Required free text, trimmed before it is measured.

    Lifted deliberately from ``resident_complaint_schemas`` rather than imported
    from it: this module carries the admin bodies and that one carries the
    resident's, and a shared private helper is how the two surfaces start
    constraining each other. The rule it encodes is the same either way --
    without ``strip_whitespace`` a title of three spaces satisfies
    ``min_length=1`` and reaches the RPC as an empty string, where the database
    refuses it correctly but three layers further in than it needed to.
    """
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=limit),
    ]


def _optional_text(limit: int) -> object:
    """Optional free text, trimmed. Absent and all-spaces both arrive as ``""``."""
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=limit)]


class StaffComplaintDetail(CamelModel):
    complaint: dict[str, Any]
    events: list[dict[str, Any]]


class UpdateComplaintRequest(CamelModel):
    """Admin edit. Every field optional; omitted fields are left unchanged."""

    status: str | None = Field(None, description="Pending | In Progress | Resolved")
    assignee: str | None = Field(None, max_length=200)
    assigned_to_membership_id: str | None = None
    progress: int | None = Field(None, ge=0, le=100)
    expected_resolution_at: datetime | None = None
    #: Free text shown to the resident on the timeline. Writes an event even when
    #: nothing else changes -- it is the admin's "Resident-visible Update" box.
    update_note: str | None = Field(None, max_length=2000)


class AddCommentRequest(CamelModel):
    """A new comment on a complaint."""

    message: str = Field(..., min_length=1, max_length=2000)
    visibility: str = Field(
        "resident",
        description="'resident' (visible to them) or 'internal' (admins only)",
    )


class AdminRaiseComplaintRequest(CamelModel):
    """What the admin portal's complaint form collects.

    The resident's form (``resident_complaint_schemas.RaiseComplaintRequest``) is
    the shape this mirrors, with one field added and one renamed.

    **Added: ``forMembershipId``.** Present means *file this against that
    resident's membership* -- the complaint becomes theirs, appears on their
    portal and keeps the resident verbs. Absent means the complaint is not
    attached to anybody's home (an amenity, a lobby, a gate) and belongs to the
    admin portal alone. That single optional field is the whole of the two modes;
    the database derives ``raisedVia`` from it rather than accepting it, because
    a client that could send both could send them contradicting each other.

    **Renamed: ``priority``, not ``urgency``.** The resident's form says
    ``urgency`` because that is the word on the resident's screen; the admin
    screens have said ``priority`` since the first complaint list. Both translate
    through ``complaint_priority_to_storage`` to the same column, so the two
    portals cannot mean different things by ``High``.

    **``expectedResolutionAt`` is absent for the same reason it is absent from
    the resident's form**, and the reason is stronger here: an admin who could
    send a deadline could quietly give the association's own complaints a
    different SLA from the residents'. The rule is in the database (§3.3).

    ``category`` is optional here, exactly as it is on the resident's form: a
    caller submitting ``skillId`` gets the trade's current name snapshotted into
    ``category`` by the RPC, and requiring both would make the admin's trade
    picker send a string it does not have. "A complaint needs a category" is
    enforced by ``admin_raise_complaint`` -- one place, for both portals -- and
    surfaces as a 422.
    """

    title: _required_text(200)  # type: ignore[valid-type]
    description: _optional_text(4000) = ""  # type: ignore[valid-type]
    #: Legacy shape; new callers send ``skillId`` and let the database snapshot
    #: that trade's current name into ``category``.
    category: _optional_text(80) = ""  # type: ignore[valid-type]
    skill_id: str | None = None
    #: ``High`` | ``Medium`` | ``Low``. The column is ``priority`` and so is this.
    priority: str = Field(default="Low")
    location: _optional_text(200) = ""  # type: ignore[valid-type]
    #: The admin's guess at whose job this is, and a **fallback only**:
    #: ``resolve_complaint_department`` tries the skill, then the category, and
    #: reaches this last. ``None`` -- "Not sure" -- routes to triage, which is
    #: the honest answer for most of what lands on this form.
    department_id: str | None = None
    #: The resident this is being filed for, from the admin snapshot's
    #: ``users[].membershipId``. Refused with a 403 when it names a membership in
    #: another community: filing it into the admin's own community instead would
    #: hand a complaint to a management team that has never heard of the person
    #: it names.
    for_membership_id: str | None = None


class AdminComplaintRaised(CamelModel):
    """The id of the complaint that was just filed.

    Deliberately not the complaint itself. The resident's raise **does** read its
    complaint back, because the response carries the SLA deadline the resident is
    about to be held to and could not have computed. The admin has no such gap:
    the admin portal's complaint list is ``GET /dashboard/snapshot``, which both
    writes on this router already refresh through the shared SSE trigger, so a
    read-back here would return a row the screen is about to receive anyway --
    and would return it through the *resident* projection, which is the wrong
    shape for the screen that asked.
    """

    id: str
    message: str
