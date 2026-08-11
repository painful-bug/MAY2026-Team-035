"""Wire models for which department owns a complaint.

Three populations touch this surface and they want three different things,
which is why there are three reads rather than one filtered one:

* an **admin** wants the complaints nobody could route — the triage queue;
* a **supervisor** wants their own department's list, and a way to say "this
  isn't ours";
* a **manager** wants the same list, plus the requests waiting on their answer.

The routing rule itself is not represented here at all. It lives in
``resolve_complaint_department`` (`0050`) and is applied when a complaint is
raised — category first, the resident's pick second, the triage queue third.
Restating it in a Python model would give it a second home free to disagree
with the first.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel


class DepartmentOption(CamelModel):
    """A department, named, for a destination picker.

    Three fields, because a picker needs three. ``GET /departments`` carries
    roster counts, categories, opening hours and skills and is admin-only for
    good reason -- widening *that* so a manager could draw a dropdown would have
    traded a real read boundary for a widget.
    """

    id: str
    name: str
    kind: str | None = None


class DepartmentComplaint(CamelModel):
    """One complaint on a department's queue.

    ``raisedBy`` and ``unitCode`` are joined in the RPC rather than fetched per
    row: a queue screen that renders fifty complaints would otherwise make fifty
    follow-up reads to answer "who, and which flat", which is the first thing
    anyone looks at.

    ``openRequestId`` is present so the screen knows a transfer has already been
    asked for. Without it the only way to draw the button correctly would be to
    read the request list and join the two client-side, and a supervisor would
    be able to file the same request twice before finding out the unique index
    refuses it.
    """

    id: str
    title: str
    description: str | None = None
    category: str | None = None
    status: str
    priority: str | None = None
    location: str | None = None
    created_at: datetime | None = None
    due_at: datetime | None = None
    resolved_at: datetime | None = None
    raised_by: str | None = None
    unit_code: str | None = None
    open_request_id: str | None = None


class UnassignedComplaint(CamelModel):
    """One complaint in the admin's triage queue.

    Narrower than ``DepartmentComplaint`` and deliberately so: this list exists
    to answer one question — *whose is this?* — and the fields that help answer
    it are the category, what was written and who wrote it. A due date on a
    complaint nobody has been given yet would be a deadline with no owner.
    """

    id: str
    title: str
    description: str | None = None
    category: str | None = None
    status: str
    priority: str | None = None
    created_at: datetime | None = None
    raised_by: str | None = None
    unit_code: str | None = None


class DepartmentChangeRequest(CamelModel):
    """A supervisor's "this belongs elsewhere", waiting on their manager.

    ``toDepartmentId`` is nullable at every layer, and that is the honest shape.
    A supervisor who knows a lift complaint is not plumbing usually does not
    know whose it is, and forcing them to name a destination would either stop
    them saying anything or make them guess.
    """

    id: str
    complaint_id: str
    complaint_title: str | None = None
    to_department_id: str | None = None
    to_department_name: str | None = None
    requested_by: str | None = None
    reason: str | None = None
    created_at: datetime | None = None


class AssignDepartmentRequest(CamelModel):
    """Allot an unrouted complaint, or move a routed one.

    One body for two different acts, because they are the same write with
    different callers: an admin answering the triage queue, and a manager moving
    work out of their own department. Which one you are is decided in Postgres
    by what the complaint currently holds, not by which endpoint you called.
    """

    department_id: str


class RequestDepartmentChangeRequest(CamelModel):
    """A supervisor asking for a complaint to be moved."""

    to_department_id: str | None = None
    reason: str | None = Field(default=None, max_length=500)


class DecideDepartmentChangeRequest(CamelModel):
    """The manager's answer.

    ``toDepartmentId`` may override what the supervisor suggested — the manager
    knows the society better and is the one being asked. Accepting with nothing
    named returns the complaint to the admin's triage queue, which is what "not
    ours, and I don't know whose either" actually means.
    """

    #: ``accept`` or ``reject``.
    decision: str
    to_department_id: str | None = None
