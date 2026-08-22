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
    #: Structural rank: ``manager`` | ``supervisor`` | ``member``. Separate from
    #: ``role`` because the seed data proves the two are not a function of each
    #: other -- two departments' heads render as 'Supervisor' and 'Manager'.
    #:
    #: Was ``head`` until 0035. Four vocabularies disagreed about this one word,
    #: and ``supervisor`` was in this docstring while being a value the CHECK
    #: constraint had never allowed -- an advertised rank no write could produce.
    #: The department's *head* is still called that everywhere the API says
    #: ``head``; that is the person holding ``rank = 'manager'``.
    rank: str = "member"
    shift: str | None = None
    status: str = "active"
    membership_id: str | None = None
    #: The service provider behind this row, when the person was hired through
    #: an application rather than typed into the department form. Null is the
    #: ordinary case and stays so -- A7 made a roster a list of names, and 0035
    #: only stopped that being the *only* thing it could be.
    #:
    #: It is here because the two things a manager can do to a roster row take
    #: two different ids: removal takes this row's ``id``, and blacklisting
    #: takes the provider's. Without this field one screen cannot offer both.
    service_provider_id: str | None = None
    #: Live work orders this person **supervises** in this department --
    #: ``work_orders.supervisor_membership_id``, everything not completed,
    #: cancelled or failed.
    #:
    #: Zero for anyone whose rank is not ``manager`` or ``supervisor``, and that
    #: is the truth rather than a placeholder: a member's real number is
    #: ``openCommitmentCount`` below.
    #:
    #: **It replaced ``activeAssignmentCount`` on 2026-08-21** (product ruling
    #: 5). That field counted open complaints by ``assigned_to_membership_id``
    #: or by a prefix match on ``assignee_label`` -- one column nothing writes
    #: (complaints are department-pooled; ruling 1 keeps it that way) and one no
    #: frontend has ever set. It was a constant zero on every row of every
    #: roster, rendered as "0 open complaints" beside a real number.
    supervised_work_order_count: int = 0
    #: Jobs and shifts still booked in their name (``0043``). Not the same
    #: number as ``supervisedWorkOrderCount``, which counts work they are
    #: accountable *for*: a supervisor holds no booking of their own, and a
    #: worker's job outlives whoever raised it.
    #:
    #: It is here because it decides which verb a roster row offers. Removal is
    #: refused while this is non-zero, so a screen that did not know the number
    #: could only find out by trying — and a manager would experience the rule
    #: as a button that sometimes errors.
    open_commitment_count: int = 0
    #: ``pending`` while a departure is open on this row, ``approved`` once the
    #: manager set a leave date that has not arrived yet, otherwise null. The
    #: engine is already (wholly or from the date) frozen against this person
    #: when it is set.
    departure_status: str | None = None
    #: The leave date the row is heading toward — the requested one while
    #: pending, the decided one once approved. Null for an undated (immediate)
    #: request. What the roster tile renders as "leaving <date>".
    departure_effective_at: datetime | None = None


class DepartmentSummary(CamelModel):
    """A department with the counts the list screen renders."""

    id: str
    name: str
    description: str | None = None
    #: Category names, which is what the frontend stores and filters on...
    categories: list[str] = Field(default_factory=list)
    #: ...paired with their ids, per the R23 label+id rule.
    category_ids: list[str] = Field(default_factory=list)

    #: Skills the department needs, chosen explicitly. **Empty by default and
    #: never inherited from ``categories``** -- the two answer different
    #: questions (which trade handles this kind of complaint, versus which
    #: trades this department employs) and inheriting one from the other would
    #: silently give every department skills nobody chose. Same label+id pairing
    #: as categories, per R23.
    skills: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)

    #: The head's name. Backed by the staff row with ``rank = 'manager'``
    #: (``'head'`` before 0035). ``head`` stays the wire word.
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

    #: Whether **this caller** may hire for **this department** --
    #: ``can_hire_for_department`` asked directly, so the screen and the RPC
    #: cannot disagree about it.
    #:
    #: Worth a field rather than a role check in the browser because the answer
    #: stopped being a property of the caller. Hiring belongs to the department's
    #: own active manager, and a community admin is the fallback **only while it
    #: has none** -- so the same admin may hire for one department and not the
    #: next one down the list. A security department's roster-ranked manager
    #: qualifies too, and they hold ``membership_role = 'security'``, which no
    #: role check in the frontend would have guessed.
    #:
    #: ``None`` means *not asked on this read*, which is the honest answer for
    #: the list: it is one round trip per department and the list has no control
    #: that needs it. Only the single-department read fills it in.
    can_hire: bool | None = None


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


class SetDepartmentSkillsRequest(CamelModel):
    """The department's whole skill set, as the form submits it.

    Ids rather than names, because by the time this is sent every skill exists:
    the form's "Add skill" button creates a new one through
    ``POST /departments/{id}/skills`` and gets an id back. A name here would be
    a second, quieter way to write to the global catalogue.
    """

    skill_ids: list[str] = Field(default_factory=list)


class AddDepartmentSkillRequest(CamelModel):
    """One skill, by name, to create if needed and attach.

    This is the only request in the API that may write to the global skill
    catalogue as a side effect, and it is deliberate: the alternative is a
    client that creates then attaches, which can half-fail and leave a skill
    nobody asked for.
    """

    name: str = Field(min_length=1, max_length=80)


