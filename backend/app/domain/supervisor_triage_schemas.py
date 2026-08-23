"""Wire models for the supervisor's triage dashboard.

The shapes here are **frozen** by ``docs/plans/SUPERVISOR_TRIAGE_SPEC.md`` and
were built against in parallel by the frontend, so a field renamed here is a
section that stops rendering rather than a compile error.

**Two DTOs and not one.** Sections 1 and 2 of the dashboard are *complaints* --
work nobody has been sent to yet -- and sections 3 and 4 are *work orders*, which
have a person and an hour attached. Folding them into one row type would mean a
model whose half the fields are null in half the sections, and a screen that has
to know which half it is looking at anyway.

**Four arrays and no bucket field.** The alternative -- one list with a
``bucket`` column -- moves the grouping into the client, where four definitions
that must agree become four places to get them wrong. The server decides;
``supervisor_triage_snapshot`` is where the definitions live, once.

``priority`` and ``status`` are the **wire** vocabulary here (``High``,
``In Progress``) and the storage vocabulary in the RPC underneath.
``app/domain/vocabularies.py`` is the seam, as it is for every other surface.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel


class TriageComplaint(CamelModel):
    """A complaint on the supervisor's dashboard: sections 1 and 2.

    ``reroutedAt`` is derived rather than stored -- the newest
    ``department_assigned`` timeline event naming this department as the
    destination. There is deliberately no column for it: a complaint can arrive
    here more than once, and the events already record every arrival with who
    and when.

    ``returnedToPoolAt``, ``reopenedCount`` and ``reroutedAt`` are the three
    "this is not as new as it looks" badges the spec freezes. All three ride on
    facts the engine already recorded; none of them is a new lifecycle state.
    """

    id: str
    title: str = ""
    #: As stored: the trade name a resident or a category mapping typed. Not a
    #: vocabulary -- the chip's colour is hashed from it on the client.
    category: str = ""
    #: ``High`` | ``Medium`` | ``Low``.
    priority: str
    #: Wire vocabulary: ``Pending``, ``In Progress``, ...
    status: str
    location: str = ""
    raised_by: str = ""
    unit_code: str | None = None
    created_at: datetime | None = None
    due_at: datetime | None = None
    returned_to_pool_at: datetime | None = None
    reopened_count: int = 0
    rerouted_at: datetime | None = None
    taken_up_at: datetime | None = None
    taken_up_by_name: str | None = None
    live_work_order_count: int = 0
    open_request_id: str | None = None


class TriageWorkOrder(CamelModel):
    """A job on the supervisor's dashboard: sections 3, 4 and 5.

    ``status`` is the **work-order** vocabulary and is passed through unmapped --
    ``draft``, ``awaiting_resident``, ``offered``, ``scheduled``,
    ``in_progress``. That is not an inconsistency with ``TriageComplaint.status``
    beside it: the two are different vocabularies for different nouns, and
    ``work_order_schemas.WorkOrder`` has always sent the storage words for this
    one. Renaming them here would give the same field two spellings depending on
    which endpoint answered.

    ``inheritedAt`` is ``work_orders.supervision_inherited_at``: this job arrived
    by somebody's removal rather than by the reader's own hand. Supervisor-only
    by construction -- no resident-facing or worker-facing read has ever returned
    a supervisor's identity, which is why re-stamping needed no notification.

    ``offeredToName`` is the other half of ``assigneeName`` and arrived with
    amendment 2's ruling A3. ``assigneeName`` is now the person who **accepted**
    and ``offeredToName`` is the person who has been asked and has not answered.
    One field carrying both would make a section-3 card read "Ravi is coming"
    about a job Ravi has not agreed to, which is the exact confusion the ruling
    exists to remove.
    """

    id: str
    complaint_id: str | None = None
    complaint_title: str = ""
    complaint_category: str = ""
    #: ``High`` | ``Medium`` | ``Low``, like the complaint's -- a job's urgency
    #: *is* the complaint's urgency (`0036` inherits it rather than copying it).
    priority: str
    status: str
    #: The worker who accepted, and nobody else.
    assignee_name: str | None = None
    #: The worker the job is currently offered to, awaiting their answer.
    offered_to_name: str | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    started_at: datetime | None = None
    inherited_at: datetime | None = None
    location_text: str | None = None
    skill_name: str | None = None


class TriageSnapshot(CamelModel):
    """One department's dashboard, in one read.

    Empty arrays and never a 404: a department with nothing in a section has an
    empty section, and a department the caller may not see is a 403 from the RPC
    rather than a snapshot that happens to be blank. An empty dashboard and a
    refused one look identical on a screen, and the difference is the whole
    content of the answer.

    **Five sections since amendment 2**, and the fifth is not a split of an old
    one so much as a correction to it: an offered job nobody has accepted was
    being shown as assigned work. ``openRequests`` sits between ``takenUp`` and
    ``assignedPending``, and *committed* -- an ``accepted`` assignment, or status
    ``scheduled`` -- is now the line between them.
    """

    department_id: str
    #: Storage status ``open``, no take-up stamp, and no live work order.
    new_complaints: list[TriageComplaint] = []
    #: Taken up, and no live work order yet.
    taken_up: list[TriageComplaint] = []
    #: Waiting on the resident: ``awaiting_resident`` and uncommitted. The sixth
    #: section, added by the 2026-08-23 ruling F1, and a split out of
    #: ``openRequests`` rather than a new fact -- a job the resident has not
    #: answered is not something the supervisor can act on, and listing it among
    #: the work they can pick up was showing them a queue that was not theirs.
    awaiting_resident: list[TriageWorkOrder] = []
    #: Raised, live, and nobody has committed: ``draft`` or ``offered``. Since
    #: 2026-08-23 this no longer carries ``awaiting_resident``, which has the
    #: section above.
    open_requests: list[TriageWorkOrder] = []
    #: A worker has accepted it (or it is booked) and has not started.
    assigned_pending: list[TriageWorkOrder] = []
    #: The worker pressed Start.
    in_progress: list[TriageWorkOrder] = []


class AddComplaintNoteRequest(CamelModel):
    """A permanent internal note for a complaint's timeline.

    Staff and workers read it; the resident does not. The bound is the
    database's own (``add_complaint_note_internal`` refuses anything outside
    1--2000 with ``HB422``), stated here as well so an empty composer is a 422
    that names the field rather than a round trip.
    """

    note: str = Field(min_length=1, max_length=2000)


class ComplaintThreadOpened(CamelModel):
    """The id of the complaint's chat thread.

    Only the id, deliberately. The dock already knows how to fetch a thread and
    its messages (`GET /messages/threads/{id}`), so returning the whole thread
    here would be a second projection of it, free to disagree with the first.
    """

    thread_id: str
