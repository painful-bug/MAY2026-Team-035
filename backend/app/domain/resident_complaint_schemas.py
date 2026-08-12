"""The resident's view of a complaint.

Separate from ``complaint_schemas``, which carries the two admin write bodies
(``UpdateComplaintRequest``, ``AddCommentRequest``) and nothing a resident sends.
The rule is 5.1 of ``docs/design/RESIDENT_BACKEND_DESIGN.md``: role is a property
of the projection, not a filter over one shared payload.

**What is deliberately absent from every model here.** ``assignedToMembershipId``
and ``departmentId`` -- who inside the association is carrying the work is an
operational fact, and a resident shown a membership id learns an identifier they
have no endpoint for. ``assigneeLabel`` *is* included: a name to ask after is the
thing a resident actually wants, and it is already the string the admin screen
displays. ``visibility`` never appears on a comment, because an internal comment
never reaches this surface at all -- the RLS policy in ``0031`` removes the row
rather than the field, which is the only version of that rule that cannot be
undone by a later refactor.

**Vocabulary.** ``status`` and ``urgency`` are the frontend's words, translated
in ``domain/vocabularies.py``. The column is ``priority``; the form says
``urgency``; neither side gets to rename the other.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.domain.common_schemas import CamelModel


def _required_text(limit: int) -> object:
    """Required free text, trimmed before it is measured.

    Without ``strip_whitespace`` a title of three spaces satisfies
    ``min_length=1`` and arrives at the RPC as an empty string, where the
    database refuses it -- correctly, but as an error raised three layers
    further in than it needed to be. The trim is what makes the model's own
    minimum mean what it says.
    """
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=limit),
    ]


def _optional_text(limit: int) -> object:
    """Optional free text, trimmed.

    An absent field and a field of spaces both arrive as ``""``, so no caller
    can tell the difference and neither can anything downstream.
    """
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=limit)]


class ComplaintSummary(CamelModel):
    """One row in the resident's complaint list.

    ``isUnread`` is per-caller, computed in ``complaint_overview`` from
    ``complaint_read_state``: it is true when the complaint has changed since
    this resident last opened it. It is the marker ``US-2.8`` asks for, and it
    could not be a column on the complaint -- two people read the same row at
    different times.

    ``isOverdue`` compares ``expectedResolutionAt`` against now in the database
    rather than here, so a client with a wrong clock cannot disagree with the
    admin's overdue count about the same complaint.
    """

    id: str
    title: str
    category: str
    #: ``Pending`` | ``In Progress`` | ``Resolved`` | ``Cancelled``.
    status: str
    #: ``High`` | ``Medium`` | ``Low``. The column is ``priority``.
    urgency: str
    location: str
    progress: int
    assignee: str
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    expected_resolution_at: datetime | None = None
    resolved_at: datetime | None = None
    is_overdue: bool
    is_unread: bool
    reopened_count: int
    comment_count: int


class ComplaintEvent(CamelModel):
    """One entry on the timeline.

    ``actor`` is the label recorded **at the time of the event**, not a lookup of
    who that membership is called today -- renaming someone should not rewrite
    what the history says they were called. ``0020`` made that decision for the
    admin timeline; this surface inherits it rather than re-deriving it.
    """

    id: str
    #: The raw ``complaint_events.event_type``, for a client that wants to pick
    #: an icon or group entries. Kept alongside ``label`` rather than replaced by
    #: it, because a UI keying off a translated string is a UI that breaks when
    #: the wording changes.
    type: str
    #: The heading a human reads -- ``Status changed``, ``Complaint reopened``.
    #: An unrecognised type falls back to the type itself: a timeline that
    #: silently omits an entry is worse than one with an ugly row, because the
    #: gap is invisible and the ugly row is a bug report.
    label: str
    actor: str
    #: The event's own words where it has any -- a reopen reason, an admin's
    #: note, a status transition rendered as text. Never a copy of the complaint.
    message: str
    created_at: datetime


class ComplaintComment(CamelModel):
    """One comment on a complaint. Public only -- see the module docstring."""

    id: str
    author: str
    message: str
    created_at: datetime


class ComplaintDetail(ComplaintSummary):
    """A complaint with everything the detail drawer renders.

    Extends the summary rather than restating it, so a field can never be
    present in a list row and missing from the detail of the same complaint.
    """

    description: str
    resolution_rating: int | None = None
    resident_feedback: str = ""
    #: Oldest first, ending at the present. Bounded, and the bound keeps the
    #: recent end -- see ``hasOlderEvents``.
    timeline: list[ComplaintEvent] = Field(default_factory=list)
    comments: list[ComplaintComment] = Field(default_factory=list)
    #: True when the complaint has more history than this response carries.
    #: Both flags are **measured**, not assumed: a bounded read that reports
    #: completeness it never checked is the one kind of truncation a client
    #: cannot detect for itself. No endpoint serves the older entries yet, so
    #: today these tell a client to say *earlier history not shown* rather than
    #: to offer a button -- which is still the difference between an incomplete
    #: record and a wrong one.
    has_older_events: bool = False
    has_older_comments: bool = False


class RaiseComplaintRequest(CamelModel):
    """What the resident's complaint form collects.

    ``expectedResolutionAt`` is **not** a field here, though the form computes
    one. The SLA is a product rule and it is applied in the database (§3.3,
    §5.3); accepting it from the client would let a resident send themselves a
    one-minute deadline and would leave the admin's ``dueAt`` and the resident's
    expectation as two independent numbers.

    Attachments are not accepted yet. The form collects them, ``media`` exists in
    the baseline, and no upload endpoint does -- so this backend takes what it
    can honour and the gap is stated in ``API.md`` rather than half-built.
    """

    title: _required_text(200)  # type: ignore[valid-type]
    description: _optional_text(4000) = ""  # type: ignore[valid-type]
    category: _required_text(80)  # type: ignore[valid-type]
    #: ``High`` | ``Medium`` | ``Low``. Defaults to ``Low``, matching the form.
    urgency: str = Field(default="Low")
    location: _optional_text(200) = ""  # type: ignore[valid-type]
    #: Which department the resident thinks this belongs to, and ``None`` when
    #: they picked "Not sure" -- which is the default and the honest answer most
    #: of the time.
    #:
    #: It is a **fallback, not an instruction**. `resolve_complaint_department`
    #: (`complaint_department_routing`) tries the category first and only reaches this when the category
    #: maps to no department: the catalogue is curated by somebody who knows how
    #: this society is organised, and the resident is guessing. So the field
    #: routes exactly the cases the catalogue cannot -- "Other", and anything
    #: nobody has mapped yet -- which is the whole reason to collect it.
    #:
    #: A department id from another community, or one that no longer exists, is
    #: ignored rather than refused. A stale form should file the complaint into
    #: the triage queue, not fail to file it.
    department_id: str | None = None


class ReopenComplaintRequest(CamelModel):
    """Why the complaint is being reopened.

    The reason is required, and by the database as well as by this model. A
    complaint that comes back with no statement of what is still wrong gives the
    admin the same row again and no new information.
    """

    reason: _required_text(2000)  # type: ignore[valid-type]


class ConfirmResolutionRequest(CamelModel):
    """The resident's verdict on a resolution.

    Rating required, feedback optional: a rating with no comment is a complete
    answer, a comment with no rating is not what ``US-2.6`` asks for.
    """

    rating: int = Field(ge=1, le=5)
    feedback: _optional_text(2000) = ""  # type: ignore[valid-type]
