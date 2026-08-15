"""The worker portal: the five verbs on a job, the calendar, the working week.

Step 6 of ``docs/plans/SERVICE_OPERATIONS_PLAN.md``, and the step that makes
``in_progress``, ``completed`` and ``failed`` reachable at all -- three statuses
that have been declared in ``work_orders_status_check`` since Step 4 with nothing
able to write them, because the only person who can say *I have started* is the
one standing at the door.

**There is no authorization decision in this file.** The three views resolve
"mine" from ``auth.uid()`` and every RPC re-checks the caller holds the
assignment, so a check here would be a second statement of the same rule with
nothing keeping the two in step. What this module does is translate vocabulary,
merge two lists into a calendar, and assemble a snapshot out of parts that
already have owners.

**The snapshot calls services rather than repositories**, following
``resident_snapshot_service``: ``service_providers_service`` decides what a
profile looks like and ``hiring_service`` decides what an engagement is, and a
home screen that re-derived either would eventually disagree with the screen it
links to.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.exceptions import NotFoundError
from app.domain.hiring_schemas import ServiceEngagement
from app.domain.worker_schemas import (
    AvailabilityRule,
    CalendarEntry,
    CompleteJobRequest,
    CreateUnavailabilityRequest,
    DeclineJobRequest,
    ReportJobFailureRequest,
    SetAvailabilityRulesRequest,
    UnavailabilityBlock,
    WorkerJob,
    WorkerJobDetail,
    WorkerSnapshot,
)
from app.repositories import notifications_repository as notifications_repo
from app.repositories import worker_repository as repo
from app.services import hiring_service, service_providers_service
from supabase import Client

#: How far ahead ``nextJob`` and the open-job count look. A worker booked further
#: out than this has a calendar to look at; the dashboard is about this fortnight.
_HORIZON_DAYS = 30

#: The most jobs any one section of the snapshot returns. A worker with more
#: offers than this open at once has a problem no page size will fix.
_SECTION_LIMIT = 20

#: Assignment states that still belong to the caller's working day. ``declined``
#: and ``withdrawn`` are history the moment they are written.
_LIVE_ASSIGNMENT = ("offered", "accepted")


def _text(value: object) -> str | None:
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


def _iso(value: datetime | None) -> str | None:
    """A datetime as PostgREST wants it, or ``None``.

    Pydantic has already parsed and validated it; this only re-renders it, so a
    naive value stays naive rather than being stamped with the server's timezone
    one layer away from where anybody would look for it.
    """
    return None if value is None else value.isoformat()


def _job_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "assignment_id": row["assignment_id"],
        "work_order_id": row["work_order_id"],
        "staff_assignment_id": _text(row.get("staff_assignment_id")),
        "assignment_status": str(row.get("assignment_status") or "offered"),
        "work_order_status": str(row.get("work_order_status") or "draft"),
        "priority": str(row.get("priority") or "medium"),
        "subject_kind": str(row.get("subject_kind") or "resident"),
        "scheduled_start_at": row.get("scheduled_start_at"),
        "scheduled_end_at": row.get("scheduled_end_at"),
        "offered_at": row.get("offered_at"),
        "responded_at": row.get("responded_at"),
        "decline_reason": _text(row.get("decline_reason")),
        "is_auto_assigned": bool(row.get("is_auto_assigned")),
        "is_forced": bool(row.get("is_forced")),
        "community_id": row["community_id"],
        "community_name": _text(row.get("community_name")),
        "department_id": _text(row.get("department_id")),
        "department_name": _text(row.get("department_name")),
        "department_kind": _text(row.get("department_kind")),
        "complaint_id": _text(row.get("complaint_id")),
        "complaint_title": _text(row.get("complaint_title")),
        "complaint_category": _text(row.get("complaint_category")),
        "skill_name": _text(row.get("skill_name")),
        "location_text": _text(row.get("location_text")),
        "failed_attempt_count": int(row.get("failed_attempt_count") or 0),
        "cancelled_reason": _text(row.get("cancelled_reason")),
    }


def _to_job(row: dict[str, Any]) -> WorkerJob:
    return WorkerJob(**_job_fields(row))


def _to_job_detail(row: dict[str, Any]) -> WorkerJobDetail:
    return WorkerJobDetail(
        **_job_fields(row),
        complaint_description=_text(row.get("complaint_description")),
        resident_name=_text(row.get("resident_name")),
        resident_phone_e164=_text(row.get("resident_phone_e164")),
        resident_unit_code=_text(row.get("resident_unit_code")),
    )


def _to_block(row: dict[str, Any]) -> UnavailabilityBlock:
    return UnavailabilityBlock(
        id=row["id"],
        starts_at=row["starts_at"],
        ends_at=row["ends_at"],
        reason=_text(row.get("reason")),
        scope=str(row.get("scope") or "provider"),
        department_name=_text(row.get("department_name")),
        created_at=row.get("created_at"),
    )


def _to_rule(row: dict[str, Any]) -> AvailabilityRule:
    return AvailabilityRule(
        id=_text(row.get("id")),
        weekday=int(row.get("weekday") or 0),
        start_time=row["start_time"],
        end_time=row["end_time"],
        effective_from=row.get("effective_from"),
        effective_to=row.get("effective_to"),
        scope=str(row.get("scope") or "provider"),
        department_name=_text(row.get("department_name")),
    )


def _read_back(client: Client, *, work_order_id: str) -> WorkerJob:
    """Re-read the job the write just touched.

    Every verb returns the row rather than the request, because the status the
    caller cares about afterwards is the one the database settled on -- an accept
    that raced and lost is a `409`, but an accept that succeeded has moved the job
    to ``scheduled`` and only the read says so.
    """
    row = repo.get_job(client, work_order_id=work_order_id)
    if row is None:
        raise NotFoundError("No such job.", code="worker_job_not_found")
    return _to_job(row)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


def list_jobs(
    client: Client,
    *,
    status: str | None = None,
    assignment_status: str | None = None,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
) -> list[WorkerJob]:
    """The caller's own jobs, soonest first."""
    return [
        _to_job(row)
        for row in repo.list_jobs(
            client,
            work_order_status=status,
            assignment_status=assignment_status,
            starts_from=_iso(starts_from),
            starts_to=_iso(starts_to),
        )
    ]


def get_job(client: Client, *, work_order_id: str) -> WorkerJobDetail:
    """One job, with the complaint in full and who to meet."""
    row = repo.get_job(client, work_order_id=work_order_id)
    if row is None:
        raise NotFoundError("No such job.", code="worker_job_not_found")
    return _to_job_detail(row)


def accept(client: Client, *, work_order_id: str) -> WorkerJob:
    """Take an offered job."""
    repo.accept_offer(client, work_order_id=work_order_id)
    return _read_back(client, work_order_id=work_order_id)


def decline(
    client: Client, *, work_order_id: str, body: DeclineJobRequest
) -> WorkerJob:
    """Say no to an offer."""
    repo.decline_offer(client, work_order_id=work_order_id, reason=body.reason)
    return _read_back(client, work_order_id=work_order_id)


def start(client: Client, *, work_order_id: str) -> WorkerJob:
    """The worker is on site."""
    repo.start_job(client, work_order_id=work_order_id)
    return _read_back(client, work_order_id=work_order_id)


def complete(
    client: Client, *, work_order_id: str, body: CompleteJobRequest
) -> WorkerJob:
    """The work is done. **Does not resolve the complaint.**"""
    repo.complete_job(client, work_order_id=work_order_id, notes=body.notes)
    return _read_back(client, work_order_id=work_order_id)


def report_failure(
    client: Client, *, work_order_id: str, body: ReportJobFailureRequest
) -> WorkerJob:
    """The visit did not happen."""
    repo.report_failure(client, work_order_id=work_order_id, reason=body.reason)
    return _read_back(client, work_order_id=work_order_id)


# ---------------------------------------------------------------------------
# The working week
# ---------------------------------------------------------------------------


def list_unavailability(
    client: Client, *, starts_from: datetime | None, starts_to: datetime | None
) -> list[UnavailabilityBlock]:
    """The caller's own leave, earliest first."""
    return [
        _to_block(row)
        for row in repo.list_unavailability(
            client, ends_after=_iso(starts_from), starts_before=_iso(starts_to)
        )
    ]


def add_unavailability(
    client: Client, *, body: CreateUnavailabilityRequest
) -> UnavailabilityBlock:
    """Mark a window unavailable, everywhere the caller works.

    The block is read back rather than composed from the request, because
    ``scope`` and ``createdAt`` are the database's to decide and a client that
    guessed them would be right until the day somebody adds a per-department
    block through another door.
    """
    block_id = repo.add_unavailability(
        client,
        starts_at=body.starts_at.isoformat(),
        ends_at=body.ends_at.isoformat(),
        reason=body.reason,
    )
    for row in repo.list_unavailability(client):
        if str(row.get("id")) == block_id:
            return _to_block(row)
    raise NotFoundError(
        "Could not read back that unavailable block.",
        code="unavailability_not_found",
    )


def delete_unavailability(client: Client, *, block_id: str) -> None:
    """Remove one of the caller's own blocks."""
    repo.delete_unavailability(client, block_id=block_id)


def list_availability_rules(client: Client) -> list[AvailabilityRule]:
    """The caller's declared working week.

    **An empty list means always available**, which is exactly what
    ``dispatch_candidates`` reads it as -- *no rules* is not *no hours*, and the
    opposite reading would make every newly hired worker invisible to the engine
    until they filled in a form.
    """
    return [_to_rule(row) for row in repo.list_availability_rules(client)]


def set_availability_rules(
    client: Client, *, body: SetAvailabilityRulesRequest
) -> list[AvailabilityRule]:
    """Replace the working week with the given set."""
    repo.set_availability_rules(
        client,
        rules=[
            {
                "weekday": rule.weekday,
                "startTime": rule.start_time.isoformat(),
                "endTime": rule.end_time.isoformat(),
                "effectiveFrom": (
                    rule.effective_from.isoformat() if rule.effective_from else None
                ),
                "effectiveTo": (
                    rule.effective_to.isoformat() if rule.effective_to else None
                ),
            }
            for rule in body.rules
        ],
    )
    return list_availability_rules(client)


def calendar(
    client: Client, *, starts_from: datetime, starts_to: datetime
) -> list[CalendarEntry]:
    """Jobs and leave in one time-ordered list.

    **A merge in Python rather than a union in SQL**, and the reason is that the
    two halves are already views with their own filters: a third statement that
    had to agree with both is one more place for "mine" to mean something
    slightly different. Two reads and a sort cost nothing at a month's scale.

    Cancelled and declined entries are dropped. A calendar is a claim about where
    somebody will be, and a job they turned down is not one.
    """
    entries = [
        CalendarEntry(
            kind="job",
            id=str(row["assignment_id"]),
            starts_at=row["scheduled_start_at"],
            ends_at=row.get("scheduled_end_at"),
            title=_text(row.get("complaint_title")) or "Scheduled work",
            subtitle=_text(row.get("location_text"))
            or _text(row.get("department_name")),
            community_id=_text(row.get("community_id")),
            community_name=_text(row.get("community_name")),
            work_order_id=str(row["work_order_id"]),
            status=str(row.get("work_order_status") or ""),
        )
        for row in repo.list_jobs(
            client, starts_from=_iso(starts_from), starts_to=_iso(starts_to)
        )
        if row.get("scheduled_start_at")
        and str(row.get("assignment_status")) in _LIVE_ASSIGNMENT
        and str(row.get("work_order_status")) != "cancelled"
    ]

    entries.extend(
        CalendarEntry(
            kind="unavailable",
            id=str(row["id"]),
            starts_at=row["starts_at"],
            ends_at=row["ends_at"],
            title=_text(row.get("reason")) or "Unavailable",
            subtitle=_text(row.get("department_name")),
            status=str(row.get("scope") or "provider"),
        )
        for row in repo.list_unavailability(
            client, ends_after=_iso(starts_from), starts_before=_iso(starts_to)
        )
    )

    entries.sort(key=lambda entry: entry.starts_at)
    return entries


# ---------------------------------------------------------------------------
# The dashboard
# ---------------------------------------------------------------------------


def snapshot(client: Client, *, profile_id: str) -> WorkerSnapshot:
    """Everything the worker's dashboard renders, in one call.

    **Takes no parameters beyond the caller's own identity**, so there is nothing
    a client could send that would widen what comes back.

    An unregistered caller gets a snapshot with a null ``provider`` rather than a
    404, and that is the difference that makes this endpoint the whole empty
    state: null provider means *show the registration form*, empty
    ``communities`` means *show the community search*, and both are answered
    without a client interpreting an error.

    Sequential reads, one honest ``generatedAt``: the offers could be a heartbeat
    older than the notification count. The two other snapshots in this API work
    the same way and for the same reason -- somebody refreshing a dashboard is
    not asking for a consistent cut of the database.
    """
    now = datetime.now(UTC)
    provider = None
    communities: list[ServiceEngagement] = []
    try:
        provider = service_providers_service.get_mine(client, profile_id=profile_id)
    except NotFoundError:
        # Not an error here, unlike on `GET /service-providers/me`. This endpoint
        # answers "what should I show this person", and "the registration form"
        # is one of its legitimate answers.
        return WorkerSnapshot(generated_at=now)

    communities = hiring_service.list_my_engagements(
        client, profile_id=profile_id, active_only=True
    )

    pending_offers = [
        _to_job(row)
        for row in repo.list_jobs(
            client, assignment_status="offered", limit=_SECTION_LIMIT
        )
    ]

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = [
        _to_job(row)
        for row in repo.list_jobs(
            client,
            assignment_status="accepted",
            starts_from=day_start.isoformat(),
            starts_to=(day_start + timedelta(days=1)).isoformat(),
            limit=_SECTION_LIMIT,
        )
    ]

    upcoming = repo.list_jobs(
        client,
        assignment_status="accepted",
        starts_from=now.isoformat(),
        starts_to=(now + timedelta(days=_HORIZON_DAYS)).isoformat(),
        limit=_SECTION_LIMIT,
    )
    # The next job is not always the first of today's: at six in the evening
    # today's list is history, and the answer to "what is next" is tomorrow.
    open_jobs = [
        row
        for row in upcoming
        if str(row.get("work_order_status")) in ("scheduled", "in_progress")
    ]

    return WorkerSnapshot(
        provider=provider,
        communities=communities,
        pending_offers=pending_offers,
        today=today,
        next_job=_to_job(open_jobs[0]) if open_jobs else None,
        open_job_count=len(open_jobs),
        is_available=provider.is_available,
        # One count, not one per community summed. Since 0041 a notification is
        # addressed to the person, so the badge on this screen and the badge on
        # any other screen this caller opens are reading the same number.
        unread_notifications=notifications_repo.unread_count(
            client, profile_id=profile_id
        ),
        generated_at=now,
    )
