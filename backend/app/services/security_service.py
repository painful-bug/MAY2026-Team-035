"""Gate operations: posts, shifts, the two registers, incidents and offline.

Row to DTO, one vocabulary translation, and the CSV writer. The authorization is
entirely in ``0040`` -- two predicates, checked inside every write function --
so nothing here decides who may act, which is the same division ``0039`` keeps
and for the same reason: a rule stated in Python beside a rule stated in SQL is
two rules that will eventually disagree.

**The credential is hashed here and nowhere else.** ``hash_secret`` is the same
function that minted ``code_hash`` when the resident created the pass
(``resident_visitor_passes_service``), so the comparison is hash to hash all the
way down and the six digits a visitor read off their phone never reach a query,
a log or a stored column in this process.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.core.tokens import hash_secret
from app.domain.security_schemas import (
    CreateShiftRequest,
    GateVerification,
    GateVerifyRequest,
    MaterialMovement,
    OfflineBundle,
    OfflinePass,
    OfflineReconcileRequest,
    OfflineReconcileResult,
    ReconcileOutcome,
    RecordIncidentRequest,
    RecordMovementRequest,
    RecordTankerRequest,
    ReturnMovementRequest,
    RosterEntry,
    SecurityIncident,
    SecurityPost,
    SecurityShift,
    UpdateIncidentRequest,
    UpdateShiftRequest,
    UpdateTankerRequest,
    UpsertPostRequest,
    WaterTankerLog,
)
from app.domain.vocabularies import (
    incident_categories,
    incident_category_to_storage,
    incident_category_to_wire,
)
from app.repositories import security_repository as repo
from supabase import Client

#: How long a cached bundle is considered good for. The RPC clamps its own
#: parameter to 48 hours; this is the default a client gets by not asking.
_BUNDLE_HOURS = 12

_SHIFT_STATUSES = ("scheduled", "active", "completed", "cancelled", "missed")
_INCIDENT_STATUSES = ("open", "acknowledged", "resolved")
_SEVERITIES = ("low", "medium", "high", "critical")
_DIRECTIONS = ("inward", "outward")


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _text(value: object) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _one_of(value: str | None, allowed: tuple[str, ...], *, field: str) -> str | None:
    """A closed vocabulary, or a 422 that names what it accepts.

    Forwarding an unknown word would reach a CHECK constraint and come back as a
    ``23514`` with the constraint's name in it, which tells a client which
    database we use and not which word to send.
    """
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered not in allowed:
        raise ValidationError(
            f"Unknown {field}: {value}. Expected one of {', '.join(allowed)}.",
            code=f"unknown_{field}",
        )
    return lowered


# --------------------------------------------------------------------------
# Posts
# --------------------------------------------------------------------------


def _to_post(row: dict[str, Any]) -> SecurityPost:
    return SecurityPost(**row)


def list_posts(client: Client, *, include_inactive: bool = False) -> list[SecurityPost]:
    return [_to_post(row) for row in repo.list_posts(
        client, include_inactive=include_inactive)]


def save_post(
    client: Client,
    *,
    membership_id: str,
    body: UpsertPostRequest,
    post_id: str | None = None,
) -> SecurityPost:
    """Create a post or change one, then read it back.

    Read back rather than echoed, the rule every write in this feature keeps:
    ``isActive`` defaults in SQL and a partial edit coalesces, so echoing the
    request would return everything except the fields the caller did not decide.
    """
    if post_id is None and not _text(body.name):
        raise ValidationError("A post needs a name.", code="post_name_required")

    saved_id = repo.upsert_post(
        client,
        membership_id=membership_id,
        payload={
            "p_post_id": post_id,
            "p_name": body.name,
            "p_location_text": body.location_text,
            "p_department_id": body.department_id,
            "p_latitude": body.latitude,
            "p_longitude": body.longitude,
            "p_is_active": body.is_active,
        },
    )
    row = repo.get_post(client, post_id=saved_id or (post_id or ""))
    if row is None:  # pragma: no cover - the RPC just wrote it
        raise NotFoundError("Post not found.", code="post_not_found")
    return _to_post(row)


# --------------------------------------------------------------------------
# Shifts
# --------------------------------------------------------------------------


def _to_shift(row: dict[str, Any]) -> SecurityShift:
    return SecurityShift(**row)


def list_shifts(
    client: Client,
    *,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    status: str | None = None,
    post_id: str | None = None,
    shift_id: str | None = None,
) -> list[SecurityShift]:
    return [
        _to_shift(row)
        for row in repo.list_shifts(
            client,
            starts_from=_isoformat(starts_from),
            starts_to=_isoformat(starts_to),
            status=_one_of(status, _SHIFT_STATUSES, field="shift_status"),
            post_id=post_id,
            shift_id=shift_id,
        )
    ]


def create_shift(
    client: Client, *, membership_id: str, body: CreateShiftRequest
) -> SecurityShift:
    shift_id = repo.schedule_shift(
        client,
        membership_id=membership_id,
        payload={
            "p_staff_assignment_id": body.staff_assignment_id,
            "p_starts_at": _isoformat(body.starts_at),
            "p_ends_at": _isoformat(body.ends_at),
            "p_post_id": body.post_id,
            "p_notes": body.notes,
        },
    )
    return _read_shift(client, shift_id=shift_id)


def update_shift(
    client: Client, *, membership_id: str, shift_id: str, body: UpdateShiftRequest
) -> SecurityShift:
    repo.update_shift(
        client,
        membership_id=membership_id,
        shift_id=shift_id,
        payload={
            "p_status": _one_of(body.status, _SHIFT_STATUSES, field="shift_status"),
            "p_starts_at": _isoformat(body.starts_at),
            "p_ends_at": _isoformat(body.ends_at),
            "p_post_id": body.post_id,
            "p_notes": body.notes,
        },
    )
    return _read_shift(client, shift_id=shift_id)


def _read_shift(client: Client, *, shift_id: str) -> SecurityShift:
    row = repo.get_shift(client, shift_id=shift_id)
    if row is None:
        raise NotFoundError("Shift not found.", code="shift_not_found")
    return _to_shift(row)


def list_roster(client: Client, *, membership_id: str) -> list[RosterEntry]:
    """The guards the shift form may offer. Gate managers only (0047)."""
    return [
        RosterEntry(
            staff_assignment_id=row["staff_assignment_id"],
            name=row["display_name"],
            phone_e164=row.get("phone_e164"),
            job_title=row.get("job_title"),
            rank=row["rank"],
            shift=row.get("shift"),
        )
        for row in repo.list_roster(client, membership_id=membership_id)
    ]


# --------------------------------------------------------------------------
# The material register — US-3.3
# --------------------------------------------------------------------------


def _to_movement(row: dict[str, Any]) -> MaterialMovement:
    return MaterialMovement(**row)


def list_movements(
    client: Client,
    *,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    direction: str | None = None,
    outstanding: bool | None = None,
) -> list[MaterialMovement]:
    return [
        _to_movement(row)
        for row in repo.list_movements(
            client,
            starts_from=_isoformat(starts_from),
            starts_to=_isoformat(starts_to),
            direction=_one_of(direction, _DIRECTIONS, field="direction"),
            outstanding=outstanding,
        )
    ]


def record_movement(
    client: Client, *, membership_id: str, body: RecordMovementRequest
) -> MaterialMovement:
    direction = _one_of(body.direction, _DIRECTIONS, field="direction")
    if body.expected_return_at is not None and not body.is_returnable:
        raise ValidationError(
            "A return date only makes sense on a returnable item.",
            code="not_returnable",
        )
    movement_id = repo.record_movement(
        client,
        membership_id=membership_id,
        payload={
            "p_direction": direction,
            "p_description": body.description,
            "p_quantity": body.quantity,
            "p_unit": body.unit,
            "p_is_returnable": body.is_returnable,
            "p_expected_return_at": _isoformat(body.expected_return_at),
            "p_carrier_name": body.carrier_name,
            "p_vehicle_number": body.vehicle_number,
            "p_unit_id": body.unit_id,
            "p_post_id": body.post_id,
            "p_notes": body.notes,
            "p_recorded_at": _isoformat(body.recorded_at),
            "p_source_client_id": body.source_client_id,
        },
    )
    return _read_movement(client, movement_id=movement_id)


def mark_returned(
    client: Client, *, membership_id: str, movement_id: str, body: ReturnMovementRequest
) -> MaterialMovement:
    repo.mark_returned(
        client,
        membership_id=membership_id,
        movement_id=movement_id,
        returned_at=_isoformat(body.returned_at),
    )
    return _read_movement(client, movement_id=movement_id)


def _read_movement(client: Client, *, movement_id: str) -> MaterialMovement:
    row = repo.get_movement(client, movement_id=movement_id)
    if row is None:
        raise NotFoundError("Register entry not found.", code="movement_not_found")
    return _to_movement(row)


# --------------------------------------------------------------------------
# The tanker log — US-3.4
# --------------------------------------------------------------------------


def _to_tanker(row: dict[str, Any]) -> WaterTankerLog:
    return WaterTankerLog(**row)


def list_tankers(
    client: Client,
    *,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    on_site: bool | None = None,
) -> list[WaterTankerLog]:
    return [
        _to_tanker(row)
        for row in repo.list_tankers(
            client,
            starts_from=_isoformat(starts_from),
            starts_to=_isoformat(starts_to),
            on_site=on_site,
        )
    ]


def record_tanker(
    client: Client, *, membership_id: str, body: RecordTankerRequest
) -> WaterTankerLog:
    log_id = repo.record_tanker(
        client,
        membership_id=membership_id,
        payload={
            "p_tanker_number": body.tanker_number,
            "p_supplier_name": body.supplier_name,
            "p_volume_litres": body.volume_litres,
            "p_driver_name": body.driver_name,
            "p_driver_phone_e164": body.driver_phone_e164,
            "p_arrived_at": _isoformat(body.arrived_at),
            "p_departed_at": _isoformat(body.departed_at),
            "p_post_id": body.post_id,
            "p_notes": body.notes,
            "p_source_client_id": body.source_client_id,
        },
    )
    return _read_tanker(client, log_id=log_id)


def update_tanker(
    client: Client, *, membership_id: str, log_id: str, body: UpdateTankerRequest
) -> WaterTankerLog:
    repo.update_tanker(
        client,
        membership_id=membership_id,
        log_id=log_id,
        payload={
            "p_departed_at": _isoformat(body.departed_at),
            "p_volume_litres": body.volume_litres,
            "p_notes": body.notes,
        },
    )
    return _read_tanker(client, log_id=log_id)


def _read_tanker(client: Client, *, log_id: str) -> WaterTankerLog:
    row = repo.get_tanker(client, log_id=log_id)
    if row is None:
        raise NotFoundError("Tanker entry not found.", code="tanker_not_found")
    return _to_tanker(row)


# --------------------------------------------------------------------------
# Incidents
# --------------------------------------------------------------------------


def _to_incident(row: dict[str, Any]) -> SecurityIncident:
    data = dict(row)
    data["category"] = incident_category_to_wire(data.get("category"))
    return SecurityIncident(**data)


def list_incidents(
    client: Client,
    *,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    status: str | None = None,
    severity: str | None = None,
) -> list[SecurityIncident]:
    return [
        _to_incident(row)
        for row in repo.list_incidents(
            client,
            starts_from=_isoformat(starts_from),
            starts_to=_isoformat(starts_to),
            status=_one_of(status, _INCIDENT_STATUSES, field="incident_status"),
            severity=_one_of(severity, _SEVERITIES, field="severity"),
        )
    ]


def record_incident(
    client: Client, *, membership_id: str, body: RecordIncidentRequest
) -> SecurityIncident:
    category = "other"
    if body.category is not None:
        stored = incident_category_to_storage(body.category)
        if stored is None:
            raise ValidationError(
                f"Unknown incident category: {body.category}. Expected one of "
                f"{', '.join(incident_categories())}.",
                code="unknown_incident_category",
            )
        category = stored

    incident_id = repo.record_incident(
        client,
        membership_id=membership_id,
        payload={
            "p_summary": body.summary,
            "p_category": category,
            "p_severity": _one_of(body.severity, _SEVERITIES, field="severity")
            or "medium",
            "p_details": body.details,
            "p_location_text": body.location_text,
            "p_post_id": body.post_id,
            "p_occurred_at": _isoformat(body.occurred_at),
            "p_source_client_id": body.source_client_id,
        },
    )
    return _read_incident(client, incident_id=incident_id)


def update_incident(
    client: Client, *, membership_id: str, incident_id: str, body: UpdateIncidentRequest
) -> SecurityIncident:
    repo.update_incident(
        client,
        membership_id=membership_id,
        incident_id=incident_id,
        payload={
            "p_status": _one_of(
                body.status, _INCIDENT_STATUSES, field="incident_status"
            ),
            "p_severity": _one_of(body.severity, _SEVERITIES, field="severity"),
            "p_details": body.details,
        },
    )
    return _read_incident(client, incident_id=incident_id)


def _read_incident(client: Client, *, incident_id: str) -> SecurityIncident:
    row = repo.get_incident(client, incident_id=incident_id)
    if row is None:
        raise NotFoundError("Incident not found.", code="incident_not_found")
    return _to_incident(row)


# --------------------------------------------------------------------------
# The gate — US-3.1's missing half, and US-3.5
# --------------------------------------------------------------------------


def verify(
    client: Client, *, membership_id: str, body: GateVerifyRequest
) -> GateVerification:
    """May this person in.

    A refusal is a **200 with a verdict**, not a 4xx. The caller asked a
    question and got an answer; *this code is not recognised* is the answer, and
    turning it into a 404 would make the gate screen's error path and its success
    path two different branches of the client for one act. The 4xx codes here are
    reserved for the guard's own problems -- not on duty, nothing presented.
    """
    row = repo.verify_credential(
        client,
        membership_id=membership_id,
        credential_hash=hash_secret(body.credential),
        presented_at=_isoformat(body.presented_at),
    )
    if not row:  # pragma: no cover - every branch of the RPC returns a row
        return GateVerification(
            verdict="not_found", detail="That code is not recognised at this gate."
        )
    return GateVerification(**row)


def offline_bundle(
    client: Client, *, membership_id: str, community_id: str, hours: int | None = None
) -> OfflineBundle:
    """The passes a gate may need while disconnected.

    ``expiresAt`` is computed here rather than stored, because it is a property
    of this download rather than of anything in the database: two guards
    downloading an hour apart get two different expiries over the same passes.
    """
    window = hours or _BUNDLE_HOURS
    rows = repo.offline_bundle(client, membership_id=membership_id, hours=window)
    now = datetime.now(timezone.utc)
    return OfflineBundle(
        generated_at=now,
        expires_at=now + timedelta(hours=window),
        community_id=community_id,
        passes=[OfflinePass(**row) for row in rows],
    )


def reconcile(
    client: Client, *, membership_id: str, body: OfflineReconcileRequest
) -> OfflineReconcileResult:
    """Replay the queue an offline gate built, one entry at a time.

    **Not one round trip.** Each entry is its own transaction, so a queue of
    forty in which the eleventh is malformed still reconciles the other
    thirty-nine -- which is the whole point of reconciling rather than
    submitting. A single batch call would make one bad row lose the lot, and the
    device has already discarded its copy by then.
    """
    outcomes: list[ReconcileOutcome] = []
    accepted = rejected = replayed = 0

    for entry in body.entries:
        row = repo.reconcile_entry(
            client,
            membership_id=membership_id,
            source_client_id=entry.source_client_id,
            credential_hash=hash_secret(entry.credential),
            presented_at=entry.presented_at.isoformat(),
            claimed_verdict=entry.claimed_verdict,
        )
        outcome = ReconcileOutcome(
            source_client_id=_text(row.get("source_client_id"))
            or entry.source_client_id,
            server_verdict=_text(row.get("server_verdict")) or "not_found",
            detail=row.get("detail"),
            was_replay=bool(row.get("was_replay")),
        )
        outcomes.append(outcome)
        if outcome.was_replay:
            replayed += 1
        elif outcome.server_verdict in ("admitted", "departed"):
            accepted += 1
        else:
            rejected += 1

    return OfflineReconcileResult(
        accepted=accepted,
        rejected=rejected,
        replayed=replayed,
        outcomes=outcomes,
    )


# --------------------------------------------------------------------------
# Exports — US-3.6
# --------------------------------------------------------------------------

#: One dataset, one header row, one accessor list. Adding a sixth is a row here
#: rather than a route, which is the whole argument for
#: ``GET /security/exports/{dataset}`` being one operation.
_DATASETS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "material-movements": (
        (
            "Recorded at", "Direction", "Description", "Quantity", "Unit",
            "Returnable", "Expected return", "Returned", "Carrier", "Vehicle",
            "Flat", "Post", "Notes",
        ),
        (
            "recorded_at", "direction", "description", "quantity", "unit",
            "is_returnable", "expected_return_at", "returned_at", "carrier_name",
            "vehicle_number", "unit_code", "post_name", "notes",
        ),
    ),
    "water-tankers": (
        (
            "Arrived at", "Departed at", "Tanker number", "Supplier", "Litres",
            "Driver", "Driver phone", "Post", "Notes",
        ),
        (
            "arrived_at", "departed_at", "tanker_number", "supplier_name",
            "volume_litres", "driver_name", "driver_phone_e164", "post_name",
            "notes",
        ),
    ),
    "incidents": (
        (
            "Occurred at", "Category", "Severity", "Status", "Summary",
            "Details", "Location", "Post", "Reported by", "Resolved at",
        ),
        (
            "occurred_at", "category", "severity", "status", "summary",
            "details", "location_text", "post_name", "reported_by_name",
            "resolved_at",
        ),
    ),
    "shifts": (
        (
            "Starts at", "Ends at", "Guard", "Rank", "Post", "Status", "Notes",
        ),
        (
            "starts_at", "ends_at", "guard_name", "guard_rank", "post_name",
            "status", "notes",
        ),
    ),
}


def export_csv(
    client: Client,
    *,
    dataset: str,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
) -> str:
    """One dataset as CSV text, oldest first.

    **Oldest first, unlike every list on this surface.** A screen wants the most
    recent thing at the top; a spreadsheet opened for an audit reads forwards
    through time, and re-sorting fifteen thousand rows by hand is the first thing
    the reader would otherwise do.

    Retention is not implemented and does not need to be (`US-3.6`): nothing this
    project writes is ever aged out, so *"six months, one year, or longer"* is
    answered by the range parameters rather than by a policy.
    """
    if dataset not in _DATASETS:
        raise ValidationError(
            f"Unknown dataset: {dataset}. Expected one of "
            f"{', '.join(_DATASETS)}.",
            code="unknown_dataset",
        )

    headers, fields = _DATASETS[dataset]
    rows = _export_rows(
        client, dataset=dataset, starts_from=starts_from, starts_to=starts_to
    )

    buffer = io.StringIO()
    # `\r\n` is what RFC 4180 specifies and what Excel expects; the default
    # `\r\n` from `csv` is already right, and `newline=""` on the StringIO is not
    # needed because nothing here is a file handle.
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell(row.get(field)) for field in fields])
    return buffer.getvalue()


def _export_rows(
    client: Client,
    *,
    dataset: str,
    starts_from: datetime | None,
    starts_to: datetime | None,
) -> list[dict[str, Any]]:
    """The rows for one dataset, oldest first.

    Reads the repository rather than the list services above, because those
    translate vocabulary for a screen and a CSV wants the row. The one exception
    is the incident category, which is translated below for the same reason it is
    translated everywhere else: `security_concern` in an audit report is our
    column name leaking into somebody's spreadsheet.
    """
    limit = 5000
    if dataset == "material-movements":
        rows = repo.list_movements(
            client,
            starts_from=_isoformat(starts_from),
            starts_to=_isoformat(starts_to),
            limit=limit,
        )
    elif dataset == "water-tankers":
        rows = repo.list_tankers(
            client,
            starts_from=_isoformat(starts_from),
            starts_to=_isoformat(starts_to),
            limit=limit,
        )
    elif dataset == "incidents":
        rows = [
            {**row, "category": incident_category_to_wire(row.get("category"))}
            for row in repo.list_incidents(
                client,
                starts_from=_isoformat(starts_from),
                starts_to=_isoformat(starts_to),
                limit=limit,
            )
        ]
    else:
        rows = repo.list_shifts(
            client,
            starts_from=_isoformat(starts_from),
            starts_to=_isoformat(starts_to),
            limit=limit,
        )
    return list(reversed(rows)) if dataset != "shifts" else rows


#: Excel, LibreOffice and Google Sheets all treat a cell beginning with one of
#: these as a formula. Every one of them is reachable from a text field a guard
#: types at the gate -- `description`, `notes`, `carrier_name`, a driver's name
#: -- so an export is a path from *anyone who can reach the gate* to *code that
#: runs when the manager opens the audit report*. `csv` quoting does not help:
#: the quotes are stripped by the spreadsheet before the formula is evaluated.
_FORMULA_LEADERS = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: object) -> str:
    """One CSV cell, safe to open in a spreadsheet.

    ``True``/``False`` become ``Yes``/``No`` because the reader is a person with
    a spreadsheet, and a bare ``TRUE`` is a literal Excel is entitled to
    reformat.

    A leading formula character is prefixed with an apostrophe, which every
    spreadsheet reads as *this is text* and drops from the display. The
    alternative -- stripping the character -- silently changes ``-5`` in a
    quantity column, and a register that alters the numbers it is auditing is
    worse than one that shows an apostrophe.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    return f"'{text}" if text.startswith(_FORMULA_LEADERS) else text
