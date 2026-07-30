"""DTOs for the departments and staff surfaces.

Field names mirror ``frontend/src/data/departments.js`` exactly -- ``head``,
``operatingHours``, ``slaHours``, ``staff[].role`` -- so the DTO layer is a
rename of the stored columns rather than a new vocabulary the frontend would
have to be taught.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.domain.common_schemas import CamelModel

#: ``HH:MM``, the only shape an ``<input type="time">`` round-trips.
_TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class OperatingHours(CamelModel):
    """One daily window.

    R8: the product collects ONE window, not a weekly schedule, so this is two
    columns on ``departments`` and not a ``department_hours`` table. Both ends
    are nullable because a department may simply not have declared them.
    """

    start: str | None = Field(None, pattern=_TIME_PATTERN, examples=["08:00"])
    end: str | None = Field(None, pattern=_TIME_PATTERN, examples=["20:00"])


class StaffMember(CamelModel):
    """One person on a department's roster.

    ``membershipId`` is nullable and usually null: C1 established that the
    frontend records only a name and a phone number, so most staff have no
    account. ``name`` is therefore authoritative and the link is the enrichment,
    not the other way round.
    """

    id: str
    name: str
    phone: str | None = None
    #: The exact string the frontend renders in ``staff[].role`` ("Technician").
    role: str | None = None
    #: Structural rank: ``member`` | ``supervisor`` | ``head``. Separate from
    #: ``role`` because the seed data proves the two are not a function of each
    #: other -- two departments' heads render as 'Supervisor' and 'Manager'.
    rank: str = "member"
    shift: str | None = None
    status: str = "active"
    membership_id: str | None = None
    #: Open complaints this member holds *in this department* (A8).
    active_assignment_count: int = 0


class DepartmentSummary(CamelModel):
    """A department with the counts the list screen renders."""

    id: str
    name: str
    description: str | None = None
    #: Category names, which is what the frontend stores and filters on...
    categories: list[str] = Field(default_factory=list)
    #: ...paired with their ids, per the R23 label+id rule.
    category_ids: list[str] = Field(default_factory=list)

    #: The head's name. Backed by the staff row with ``rank = 'head'``.
    head: str | None = None
    head_staff_id: str | None = None
    email: str | None = None
    phone: str | None = None
    operating_hours: OperatingHours = Field(default_factory=OperatingHours)
    sla_hours: int | None = None
    #: ``service`` | ``security``. Security departments carry shift-based staff.
    kind: str = "service"
    #: ``Active`` | ``Inactive`` (stored as active/archived -- see A6).
    status: str = "Active"

    staff_count: int = 0
    active_complaint_count: int = 0
    resolved_complaint_count: int = 0
    overdue_complaint_count: int = 0

    created_at: datetime
    updated_at: datetime


class DepartmentDetail(DepartmentSummary):
    """A department plus its roster."""

    staff: list[StaffMember] = Field(default_factory=list)


class StaffMemberInput(CamelModel):
    """A staff member as submitted by the department form.

    ``id`` is optional: the frontend generates a local id for new rows and keeps
    the server id for existing ones, so presence is what distinguishes an update
    from an insert.
    """

    id: str | None = None
    name: str = Field(..., min_length=1, max_length=120)
    phone: str | None = Field(None, max_length=32)
    role: str | None = Field(None, max_length=60)
    shift: str | None = Field(None, description="Day | Evening | Night")
    status: str | None = Field(None, description="active | inactive")

    @field_validator("id")
    @classmethod
    def _blank_id_is_none(cls, value: str | None) -> str | None:
        """The create form seeds ``id: ''``; an empty string is not an id."""
        return value or None


class CreateDepartmentRequest(CamelModel):
    """Create a department, its category claims and its roster in one call."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    #: Category NAMES. Unknown names are created (see migration 0014, note 3),
    #: because one of the two create screens is a free-text box we cannot change.
    categories: list[str] = Field(default_factory=list)
    head: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=32)
    operating_hours: OperatingHours | None = None
    sla_hours: int | None = Field(None, gt=0, le=8760)
    kind: str | None = Field(None, description="service | security")
    status: str | None = Field(None, description="Active | Inactive")
    staff: list[StaffMemberInput] = Field(default_factory=list)


class UpdateDepartmentRequest(CamelModel):
    """Partial update. An omitted field is left alone; an explicit ``null``
    clears it.

    The distinction is real and is preserved all the way to Postgres: the service
    sends only the keys that were set, and the RPC tests ``patch ? 'key'``.
    Sending ``staff`` replaces the whole roster; omitting it leaves it untouched.
    """

    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    categories: list[str] | None = None
    head: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=32)
    operating_hours: OperatingHours | None = None
    sla_hours: int | None = Field(None, gt=0, le=8760)
    kind: str | None = Field(None, description="service | security")
    status: str | None = Field(None, description="Active | Inactive")
    staff: list[StaffMemberInput] | None = None


class ReplaceStaffRequest(CamelModel):
    """The whole roster, as the department form submits it.

    Members not listed are deactivated rather than deleted (A7) -- a complaint's
    ``assignee`` records staff by name, so a deleted row turns a past assignment
    into an unexplained string.
    """

    staff: list[StaffMemberInput] = Field(default_factory=list)


class UpdateStaffMemberRequest(CamelModel):
    """Patch one roster entry."""

    name: str | None = Field(None, min_length=1, max_length=120)
    phone: str | None = Field(None, max_length=32)
    role: str | None = Field(None, max_length=60)
    shift: str | None = Field(None, description="Day | Evening | Night")
    status: str | None = Field(None, description="active | inactive")


