"""Wire models for gate operations: posts, shifts, the registers and offline.

**The credential never appears in this module as plaintext except once.**
``GateVerifyRequest.credential`` is what the guard scanned or typed, and it is
hashed in the service before it reaches the repository -- so it exists in one
field, on one request, and in nothing that is stored, logged or returned. The
offline bundle carries hashes only, for the same reason: there is no plaintext
code anywhere in the database to hand out even if we wanted to.

**One category vocabulary, translated at the seam.** An incident's ``category``
is ``Security concern`` on the wire, because that is the word
``SecurityDashboard.jsx`` has always sent, and ``security_concern`` in the
column. ``app/domain/vocabularies.py`` holds the map, as it does for complaint
statuses and comment visibility.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.domain.common_schemas import CamelModel

# --------------------------------------------------------------------------
# Posts
# --------------------------------------------------------------------------


class SecurityPost(CamelModel):
    """A place a guard is stationed."""

    id: str
    community_id: str
    department_id: str | None = None
    name: str
    location_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None


class UpsertPostRequest(CamelModel):
    """Create a post, or change one.

    Every field except ``name`` is optional on create and on edit, and an
    omitted field on edit leaves the stored value alone rather than blanking it
    -- the RPC coalesces. A partial edit is the normal case on a form with six
    fields and one that changed.
    """

    name: str | None = Field(default=None, max_length=120)
    location_text: str | None = Field(default=None, max_length=200)
    department_id: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_active: bool | None = None


# --------------------------------------------------------------------------
# Shifts
# --------------------------------------------------------------------------


class SecurityShift(CamelModel):
    """A guard at a post for a window."""

    id: str
    community_id: str
    department_id: str | None = None
    post_id: str | None = None
    post_name: str | None = None
    staff_assignment_id: str
    guard_name: str | None = None
    guard_phone_e164: str | None = None
    guard_job_title: str | None = None
    #: ``manager`` | ``supervisor`` | ``member`` -- the roster rank, not the
    #: membership role. D3 made those separate axes.
    guard_rank: str | None = None
    starts_at: datetime
    ends_at: datetime
    #: ``scheduled`` | ``active`` | ``completed`` | ``cancelled`` | ``missed``.
    status: str = "scheduled"
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class CreateShiftRequest(CamelModel):
    """Put a guard on a post for a window."""

    staff_assignment_id: str
    starts_at: datetime
    ends_at: datetime
    post_id: str | None = None
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _ends_after_it_starts(self) -> CreateShiftRequest:
        if self.ends_at <= self.starts_at:
            raise ValueError("A shift ends after it starts.")
        return self


class UpdateShiftRequest(CamelModel):
    """Change a shift, or start and end one.

    A guard may send ``status`` alone for their *own* shift -- which is what
    ``SecurityLayout.jsx``'s *End Shift & Logout* does. Every other field, and
    anybody else's shift, is the security manager's, and ``0040`` 9 decides
    which of the two guards applies from the shape of the request rather than
    from a flag the client sets.
    """

    status: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    post_id: str | None = None
    notes: str | None = Field(default=None, max_length=500)


class RosterEntry(CamelModel):
    """One guard the shift form may roster. 0047.

    ``name`` rather than ``displayName``, matching what every other roster
    read on the frontend already calls it. ``rank`` is the roster rank
    (``manager`` | ``supervisor`` | ``member``); ``shift`` is the preference
    label 0035 constrains (``Day``, ``Night``, ...) and not a
    ``security_shifts`` row.
    """

    staff_assignment_id: str
    name: str
    phone_e164: str | None = None
    job_title: str | None = None
    rank: str
    shift: str | None = None


# --------------------------------------------------------------------------
# Registers
# --------------------------------------------------------------------------


class MaterialMovement(CamelModel):
    """One inward or outward movement. US-3.3."""

    id: str
    community_id: str
    #: ``inward`` | ``outward``.
    direction: str
    description: str
    quantity: float | None = None
    unit: str | None = None
    is_returnable: bool = False
    expected_return_at: datetime | None = None
    returned_at: datetime | None = None
    carrier_name: str | None = None
    vehicle_number: str | None = None
    unit_id: str | None = None
    unit_code: str | None = None
    post_id: str | None = None
    post_name: str | None = None
    notes: str | None = None
    recorded_at: datetime
    #: Derived in the view, never stored: a flag somebody has to flip at
    #: midnight is wrong until they do.
    is_outstanding: bool = False
    is_overdue: bool = False


class RecordMovementRequest(CamelModel):
    """Write one register entry."""

    direction: str
    description: str = Field(min_length=1, max_length=500)
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=40)
    is_returnable: bool = False
    expected_return_at: datetime | None = None
    carrier_name: str | None = Field(default=None, max_length=120)
    vehicle_number: str | None = Field(default=None, max_length=40)
    unit_id: str | None = None
    post_id: str | None = None
    notes: str | None = Field(default=None, max_length=500)
    recorded_at: datetime | None = None
    #: The id the device generated. Replaying the same one returns the original
    #: row rather than writing a second.
    source_client_id: str | None = Field(default=None, max_length=120)


class ReturnMovementRequest(CamelModel):
    """The returnable item came back."""

    returned_at: datetime | None = None


class WaterTankerLog(CamelModel):
    """One tanker at the gate. US-3.4."""

    id: str
    community_id: str
    supplier_name: str | None = None
    tanker_number: str
    volume_litres: int | None = None
    driver_name: str | None = None
    driver_phone_e164: str | None = None
    arrived_at: datetime
    departed_at: datetime | None = None
    post_id: str | None = None
    post_name: str | None = None
    notes: str | None = None
    is_on_site: bool = False


class RecordTankerRequest(CamelModel):
    """Log a tanker arriving."""

    tanker_number: str = Field(min_length=1, max_length=40)
    supplier_name: str | None = Field(default=None, max_length=120)
    volume_litres: int | None = Field(default=None, gt=0)
    driver_name: str | None = Field(default=None, max_length=120)
    driver_phone_e164: str | None = Field(default=None, max_length=20)
    arrived_at: datetime | None = None
    departed_at: datetime | None = None
    post_id: str | None = None
    notes: str | None = Field(default=None, max_length=500)
    source_client_id: str | None = Field(default=None, max_length=120)


class UpdateTankerRequest(CamelModel):
    """Record the departure, or correct the volume."""

    departed_at: datetime | None = None
    volume_litres: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=500)


class SecurityIncident(CamelModel):
    """Something worth a record."""

    id: str
    community_id: str
    #: The display vocabulary -- ``Security concern``, ``Fire alarm``. The column
    #: stores snake case; see the module docstring.
    category: str
    #: ``low`` | ``medium`` | ``high`` | ``critical``.
    severity: str = "medium"
    #: ``open`` | ``acknowledged`` | ``resolved``.
    status: str = "open"
    summary: str
    details: str | None = None
    location_text: str | None = None
    post_id: str | None = None
    post_name: str | None = None
    occurred_at: datetime
    resolved_at: datetime | None = None
    reported_by_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class RecordIncidentRequest(CamelModel):
    """File an incident."""

    summary: str = Field(min_length=1, max_length=300)
    category: str | None = None
    severity: str | None = None
    details: str | None = Field(default=None, max_length=4000)
    location_text: str | None = Field(default=None, max_length=200)
    post_id: str | None = None
    occurred_at: datetime | None = None
    source_client_id: str | None = Field(default=None, max_length=120)


class UpdateIncidentRequest(CamelModel):
    """Acknowledge, re-grade or resolve an incident."""

    status: str | None = None
    severity: str | None = None
    details: str | None = Field(default=None, max_length=4000)


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


class GateVerifyRequest(CamelModel):
    """What the guard scanned or typed."""

    #: The six-digit security code or the QR token. Hashed in the service; it
    #: reaches neither the database nor a log in this form.
    credential: str = Field(min_length=1, max_length=200)
    #: When it was presented. Defaults to now, and is only worth sending for an
    #: entry that was queued while the device was offline.
    presented_at: datetime | None = None


class GateVerification(CamelModel):
    """The answer a guard acts on.

    ``verdict`` is the field to branch on. ``admitted`` and ``departed`` both
    mean *let them through* -- the second scan of one credential is the way out,
    which is why there is no separate check-out call.
    """

    #: ``admitted`` | ``departed`` | ``refused`` | ``expired`` |
    #: ``not_yet_valid`` | ``not_found``.
    verdict: str
    #: One sentence, written for the person standing at the barrier.
    detail: str
    pass_id: str | None = None
    visitor_name: str | None = None
    guest_count: int | None = None
    unit_code: str | None = None
    resident_name: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class OfflinePass(CamelModel):
    """One pass in the offline bundle. Hashes, never a code."""

    pass_id: str
    code_hash: str | None = None
    pass_hash: str | None = None
    visitor_name: str
    guest_count: int = 1
    unit_code: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class OfflineBundle(CamelModel):
    """What a gate device caches for a disconnection.

    ``expiresAt`` is the only control on the bundle and it is deliberately the
    only one: a signature the device checks against a key the device holds is
    theatre, because the same person who can edit the cache can delete the
    check. What makes an offline admission safe is that it is **provisional
    until reconciled** -- see ``POST /security/offline-reconcile``.
    """

    generated_at: datetime
    expires_at: datetime
    community_id: str
    #: SHA-256, hex. Stated so a client cannot guess wrong.
    hash_algorithm: str = "sha256"
    passes: list[OfflinePass] = Field(default_factory=list)


class OfflineEntry(CamelModel):
    """One admission the device recorded while it was disconnected."""

    #: The device's own id for this entry. The idempotency key -- submitting the
    #: same one twice returns the first verdict rather than re-running it.
    source_client_id: str = Field(min_length=1, max_length=120)
    credential: str = Field(min_length=1, max_length=200)
    presented_at: datetime
    #: What the device decided at the time, if it decided anything. Recorded
    #: beside the server's verdict so a disagreement is visible.
    claimed_verdict: str | None = None


class OfflineReconcileRequest(CamelModel):
    """The queue, replayed."""

    entries: list[OfflineEntry] = Field(min_length=1, max_length=200)


class ReconcileOutcome(CamelModel):
    """What the server made of one queued entry."""

    source_client_id: str
    server_verdict: str
    detail: str | None = None
    #: True when this entry had already been reconciled. Not an error: a device
    #: that lost its connection mid-upload is expected to send the queue again.
    was_replay: bool = False


class OfflineReconcileResult(CamelModel):
    """The whole queue's outcome, plus the count that matters."""

    accepted: int
    rejected: int
    replayed: int
    outcomes: list[ReconcileOutcome] = Field(default_factory=list)
