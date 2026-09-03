"""Regression battery for GitHub issue #48 -- the five amenity defects.

Every test here began as an ``xfail(strict=True)`` repro of a live defect. All
twelve are fixed and promoted: each one now asserts the repaired behaviour and
fails the moment the defect comes back. Nothing in this file repairs anything --
the fixes live in ``app/domain/schemas.py``, ``app/services/amenities_service.py``,
``app/services/dashboard_service.py`` and the two repositories.

What every one of them is really guarding is a JOIN between two texts that no
type checker sees across: the SQL that the hosted database runs, and the Python
that talks to it. A key name, a status spelling or a column list can drift on
one side and the other keeps running -- silently, and wrongly, which is how all
five defects shipped.

The SQL side is read out of the migration texts the way
``test_migration_directory_is_fresh_appliable.py`` does -- whole-line ``--``
comments stripped first, values extracted by regex -- so each assertion compares
what the database actually accepts against what the Python service actually
sends. The Python side is captured by monkeypatching the repository boundary
and calling the real service functions, never by retyping the payloads here.

Diagnosis key (from the issue-#48 recon), with what each one is now:
  D1  catalogue toggle refetched the snapshot three times (frontend twin suite)
  D2  image / opening hours could not be written or projected -- now three
      fields on ``AmenityWrite``, four real columns in the legacy read/write,
      and three more keys on the snapshot projection
  D3  admin blocks are stored as status='approved' + booking_type='blocked';
      the timeline reads the TYPE now, so a block paints as one
  D4  status vocabulary drift: the phantom 'confirmed'/'blocked' statuses are
      gone, wire statuses are lowercase machine values, every RPC payload uses
      the keys its function reads, and the report KPIs are the six the
      aggregate computes
  D5  resident-facing reads routed through the admin-guarded snapshot
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from datetime import date

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ValidationError
from app.domain.amenity_schemas import (
    AddChargeRequest,
    RecordAmenityPaymentRequest,
    RefundDepositRequest,
)
from app.domain.schemas import AmenityWrite
from app.domain.vocabularies import booking_status_to_storage
from app.repositories import amenities_repository
from app.services import amenities_service, dashboard_service

BACKEND = Path(__file__).parents[1]
MIGRATIONS = BACKEND / "supabase" / "migrations"
BASELINE = MIGRATIONS / "0001_baseline.sql"
AMENITIES_MIGRATION = MIGRATIONS / "0023_amenities_on_baseline.sql"


# ---------------------------------------------------------------------------
# SQL text helpers -- same precedent as the fresh-apply suite: strip whole-line
# comments so no assertion reads a header's prose, then extract by regex.
# ---------------------------------------------------------------------------
def _statements(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def _baseline_sql() -> str:
    return _statements(BASELINE.read_text(encoding="utf-8"))


def _amenities_sql() -> str:
    return _statements(AMENITIES_MIGRATION.read_text(encoding="utf-8"))


def booking_status_enum() -> frozenset[str]:
    """The values of ``public.booking_status`` -- the only statuses a booking
    row can hold, because ``amenity_bookings.status`` is typed as this enum."""
    match = re.search(
        r"create type public\.booking_status as enum \(([^)]*)\)",
        _baseline_sql(),
        re.I,
    )
    assert match is not None, "booking_status enum not found in 0001_baseline.sql"
    values = frozenset(re.findall(r"'([\w-]+)'", match.group(1)))
    assert values, "booking_status enum parsed empty -- the regex is broken"
    return values


def series_status_vocabulary() -> frozenset[str]:
    """The values ``amenity_booking_overview.series_status`` can emit: the
    ``then``/``else`` arms of its case expression."""
    match = re.search(
        r"select case((?:.|\n)*?)end as series_status", _amenities_sql(), re.I
    )
    assert match is not None, "series_status case expression not found in 0023"
    body = match.group(1)
    values = frozenset(
        re.findall(r"then\s+'([\w-]+)'", body, re.I)
        + re.findall(r"else\s+'([\w-]+)'", body, re.I)
    )
    assert values, "series_status vocabulary parsed empty"
    return values


def booking_type_check_values() -> frozenset[str]:
    """The values ``amenity_bookings_type_check`` accepts for booking_type."""
    match = re.search(
        r"add constraint amenity_bookings_type_check\s*"
        r"check \(booking_type in \(([^)]*)\)\)",
        _amenities_sql(),
        re.I,
    )
    assert match is not None, "amenity_bookings_type_check not found in 0023"
    values = frozenset(re.findall(r"'([\w-]+)'", match.group(1)))
    assert values, "booking_type CHECK values parsed empty"
    return values


def rpc_payload_keys(name: str) -> frozenset[str]:
    """Every ``p_payload`` key the named RPC reads (``->>``, ``->`` or ``?``)."""
    match = re.search(
        rf"create or replace function public\.{name}\b((?:.|\n)*?)end \$\$;",
        _amenities_sql(),
        re.I,
    )
    assert match is not None, f"{name} not found in 0023"
    keys = frozenset(
        re.findall(r"p_payload\s*(?:->>|->|\?)\s*'([\w-]+)'", match.group(1))
    )
    assert keys, f"{name} reads no p_payload keys -- the regex is broken"
    return keys


def report_kpi_keys() -> frozenset[str]:
    """The keys of the ``kpis`` object ``amenity_report_totals`` returns."""
    text = _amenities_sql()
    start = text.index("'kpis'")
    end = text.index("'rows'", start)
    keys = frozenset(re.findall(r"'(\w+)'\s*,", text[start:end])) - {"kpis"}
    assert keys, "kpis keys parsed empty -- the regex is broken"
    return keys


# ---------------------------------------------------------------------------
# Row fixtures -- the shapes the views actually emit, copied from
# test_amenity_mapping.py so the mappers run over realistic input.
# ---------------------------------------------------------------------------
def _booking_row(**overrides: object) -> dict:
    """A row of ``amenity_booking_overview``."""
    row = {
        "id": "occurrence-1",
        "community_id": "community-1",
        "booking_series_id": "series-1",
        "amenity_id": "amenity-gym",
        "amenity_name": "Clubhouse Gym",
        "booking_mode": "shared",
        "booking_date": "2026-07-31",
        "starts_at": "07:00:00",
        "ends_at": "09:00:00",
        "is_exclusive": False,
        "buffer_minutes": 15,
        "occupant_count": 1,
        "status": "pending",
        "stored_status": "pending",
        "cancelled_at": None,
        "cancellation_reason_code": None,
        "cancellation_reason": None,
        "cancelled_by_resident": False,
        "force_cancelled": False,
        "version": 1,
        "created_at": "2026-07-30T08:15:00+00:00",
        "updated_at": "2026-07-30T08:15:00+00:00",
        "title": "Morning Fitness Session",
        "booking_type": "resident",
        "source": "resident",
        "is_private": False,
        "requires_approval": True,
        "guest_count": 0,
        "notes": None,
        "charge_override": None,
        "department": None,
        "series_status": "pending",
        "requested_at": "2026-07-30T08:15:00+00:00",
        "approved_at": None,
        "rejected_at": None,
        "rejection_reason": None,
        "rejection_reason_code": None,
        "unit_id": "unit-1",
        "unit_code": "B-1204",
        "tower": "B",
        "requested_by_membership_id": "u1",
        "resident_profile_id": "profile-1",
        "resident_name": "Aakash S.",
        "day_count": 1,
    }
    row.update(overrides)
    return row


def _ledger_row(**overrides: object) -> dict:
    """A row of ``amenity_ledger_overview``."""
    row = {
        "id": "occurrence-1",
        "community_id": "community-1",
        "booking_id": "occurrence-1",
        "booking_series_id": "series-1",
        "amenity_id": "amenity-gym",
        "amenity_name": "Clubhouse Gym",
        "unit_id": "unit-1",
        "unit_code": "B-1204",
        "resident_profile_id": "profile-1",
        "resident_name": "Aakash S.",
        "requested_by_membership_id": "u1",
        "booking_date": "2026-07-18",
        "starts_at": "07:00:00",
        "ends_at": "09:00:00",
        "booking_type": "resident",
        "title": "Resident Booking",
        "notes": "Completed without incident.",
        "booking_status": "completed",
        "force_cancelled": False,
        "cancelled_at": None,
        "cancellation_reason": None,
        "approved_at": "2026-07-17T07:45:00+00:00",
        "created_at": "2026-07-16T08:00:00+00:00",
        "updated_at": "2026-07-18T09:00:00+00:00",
        "payment_reference": "PAY-GYM-1001",
        "deposit_amount": "500.00",
        "deposit_paid": "500.00",
        "booking_charges": "1000.00",
        "additional_charges": "100.00",
        "amount_paid": "1100.00",
        "refund_amount": "0.00",
        "damage_amount": "0.00",
        "total_amount": "1100.00",
        "outstanding_deposit": "0.00",
        "remaining_refund": "500.00",
        "payment_status": "refund_pending",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# A recording stand-in for the PostgREST query builder, so the repository's
# real filter-building code runs and its filters can be inspected.
# ---------------------------------------------------------------------------
class _RecordingQuery:
    def __init__(self) -> None:
        self.in_calls: list[tuple[str, list]] = []

    def in_(self, column: str, values: list) -> "_RecordingQuery":
        self.in_calls.append((column, list(values)))
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=[], count=0)

    def __getattr__(self, name: str):
        # select / eq / gte / lte / ilike / order / range / limit / not_ ...
        # -- every other builder method chains without recording.
        def _chain(*args: object, **kwargs: object) -> "_RecordingQuery":
            return self

        return _chain


class _RecordingClient:
    def __init__(self) -> None:
        self.queries: list[_RecordingQuery] = []

    def table(self, name: str) -> _RecordingQuery:
        query = _RecordingQuery()
        self.queries.append(query)
        return query


def _patch_read_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """The money endpoints read the ledger row back after every write; feed
    that read-back a canned row so the write path can be exercised alone."""
    monkeypatch.setattr(
        amenities_service.repo,
        "get_ledger_row",
        lambda client, community_id, occurrence_id: _ledger_row(),
    )
    monkeypatch.setattr(
        amenities_service.repo,
        "list_financial_events",
        lambda client, community_id, occurrence_ids: {},
    )


# ---------------------------------------------------------------------------
# 1. D4/D3 -- every status the timeline filter names exists in the enum
# ---------------------------------------------------------------------------
def test_timeline_filter_statuses_exist_in_the_enum() -> None:
    """``timeline_only`` filters on statuses a row can actually hold.

    It used to name 'confirmed' and 'blocked' beside 'approved', and
    ``public.booking_status`` has neither: no row can be 'confirmed', and an
    admin block is an APPROVED row wearing ``booking_type = 'blocked'``. The
    filter is 'approved' alone now -- which still returns the blocks, because
    that is what they are stored as, and the timeline paints them from the type.
    """
    client = _RecordingClient()
    amenities_repository.list_bookings(client, "community-1", timeline_only=True)

    timeline_filters = [
        values
        for query in client.queries
        for column, values in query.in_calls
        if column == "stored_status"
    ]
    assert timeline_filters, "timeline_only sent no stored_status filter"
    assert set(timeline_filters[0]) <= booking_status_enum()


# ---------------------------------------------------------------------------
# 2. D4 -- every series_status the approvals filter names can occur
# ---------------------------------------------------------------------------
def test_approved_filter_values_exist_in_the_series_vocabulary() -> None:
    """The 'approved' approvals tab filters on a value the view can emit.

    It used to send ('approved', 'confirmed'); 'confirmed' is in neither
    ``public.booking_status`` nor the view's ``series_status`` case expression,
    so half of that filter could never match anything. The product ruling is
    that the tab SET stays as it is -- this is the phantom leaving, not a tab.
    """
    # list_series_first_days filters on the view's series_status column, whose
    # vocabulary is the case expression in 0023 -- so that is the set the
    # filter values must belong to. ('confirmed' is absent from the
    # booking_status enum as well; either reading fails on the same value.)
    assert set(amenities_service._APPROVAL_FILTERS["approved"]) <= (
        series_status_vocabulary()
    )


# ---------------------------------------------------------------------------
# 3. D4 -- the service's booking types are the CHECK constraint's
# ---------------------------------------------------------------------------
def test_service_booking_types_pass_the_check_constraint() -> None:
    """Every type the service will store is one the column accepts.

    ``_BOOKING_TYPES`` used to be the admin form's wording -- 'private-event',
    'society-event', 'maintenance-reservation' -- and
    ``amenity_bookings_type_check`` accepts none of the three, so three of the
    four options the form offered were rejected by Postgres on insert. The form
    keeps its wording; ``_storage_booking_type`` folds it onto the four legal
    values before validation (see the test below).
    """
    assert set(amenities_service._BOOKING_TYPES) <= booking_type_check_values()


def test_the_event_form_vocabulary_maps_onto_a_legal_booking_type() -> None:
    """The mapping is code-only: no migration, no CHECK change.

    Both event kinds are ADMIN bookings as far as the column is concerned, and
    which kind it was keeps living in the title, notes and department -- where
    the form already puts it. An unknown type is a 422, not a Postgres error.
    """
    mapped = {
        wording: amenities_service._storage_booking_type(wording)
        for wording in (
            "private-event",
            "society-event",
            "maintenance-reservation",
            "resident",
        )
    }
    assert mapped == {
        "private-event": "admin",
        "society-event": "admin",
        "maintenance-reservation": "maintenance",
        "resident": "resident",
    }
    assert set(mapped.values()) <= booking_type_check_values()

    with pytest.raises(ValidationError):
        amenities_service._storage_booking_type("gala-dinner")


# ---------------------------------------------------------------------------
# 4. RPC payload keys -- the keys Python sends are the keys SQL reads
#
# Each of these compares the payload the real service function builds against
# the ``p_payload`` keys the real SQL function reads. A key on one side and not
# the other is not an error anywhere: jsonb takes any key, and reads a missing
# one as NULL. That is exactly how all four of these shipped.
# ---------------------------------------------------------------------------
def test_record_payment_sends_keys_the_rpc_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The payment reference reaches the key the RPC dedupes on.

    ``record_amenity_payment`` reads ``reference``; the service sent
    ``payment_reference``, so the idempotency lookup saw NULL every time and a
    replayed gateway callback double-credited. ``charge_type`` and ``method``
    have no column on a financial event, so they fold into ``notes`` -- sending
    them under their own names lost them silently.
    """
    captured: dict = {}

    def _capture(client, occurrence_id, payload):
        captured.update(payload)
        return "event-1"

    _patch_read_back(monkeypatch)
    monkeypatch.setattr(amenities_service.repo, "record_payment", _capture)

    amenities_service.record_payment(
        None,
        "u1",
        "occurrence-1",
        RecordAmenityPaymentRequest(
            amount=500,
            charge_type="deposit",
            method="upi",
            payment_reference="PAY-GYM-1001",
            notes="August deposit",
        ),
    )
    assert captured, "the service never called the repository"
    assert set(captured) <= rpc_payload_keys("record_amenity_payment")
    # Subset alone would be satisfied by sending nothing but the amount, so:
    # the reference has to be under the key the RPC dedupes on, and the two
    # fields with nowhere else to go have to still be readable in the note.
    assert captured["reference"] == "PAY-GYM-1001"
    assert "deposit" in captured["notes"] and "upi" in captured["notes"]
    assert "August deposit" in captured["notes"]


def test_add_charge_sends_keys_the_rpc_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The charge description reaches the column it is written into.

    ``add_amenity_charge`` inserts ``p_payload ->> 'label'`` into
    ``amenity_booking_charges.label``; the service sent ``description``, so
    every added charge landed labelled NULL. The RPC hardcodes the charge_type
    column to 'additional', so the requested type folds into the note instead --
    a late-cancellation fee should still say that it is one.
    """
    captured: dict = {}

    def _capture(client, occurrence_id, payload):
        captured.update(payload)
        return "charge-1"

    _patch_read_back(monkeypatch)
    monkeypatch.setattr(amenities_service.repo, "add_charge", _capture)

    amenities_service.add_charge(
        None,
        "u1",
        "occurrence-1",
        AddChargeRequest(
            amount=250, charge_type="late_cancellation", description="Housekeeping"
        ),
    )
    assert captured, "the service never called the repository"
    assert set(captured) <= rpc_payload_keys("add_amenity_charge")
    assert captured["label"] == "Housekeeping"
    assert "late_cancellation" in captured["notes"]


def test_report_filters_send_keys_the_rpc_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The report window reaches the RPC under the names it reads.

    ``amenity_report_totals`` reads ``from_date`` and ``to_date`` and nothing
    else. The service sent ``start_date``/``end_date`` plus ``amenity_id`` and
    ``booking_status``, so the RPC fell back to its default window and every KPI
    described the last 30 days of the whole community whatever the admin picked.
    The two filters the RPC cannot express are applied Python-side, to the
    ledger page -- which is where they can be honest about what they narrow.
    """
    captured: dict = {}
    ledger_filters: dict = {}

    def _capture(client, community_id, payload):
        captured.update(payload)
        return {}

    def _capture_ledger(client, community_id, **kwargs):
        ledger_filters.update(kwargs)
        return [], 0

    monkeypatch.setattr(amenities_service.repo, "fetch_report_totals", _capture)
    monkeypatch.setattr(amenities_service.repo, "list_ledger", _capture_ledger)
    monkeypatch.setattr(
        amenities_service.repo, "list_amenities", lambda *args, **kwargs: ([], 0)
    )

    amenities_service.build_report(
        None,
        "u1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 22),
        amenity_id="amenity-gym",
        booking_status="approved",
    )
    assert captured, "the service never called the RPC"
    assert set(captured) <= rpc_payload_keys("amenity_report_totals")
    assert captured == {"from_date": "2026-08-01", "to_date": "2026-08-22"}
    # The two the RPC cannot take are not dropped -- they narrow the rows.
    assert ledger_filters["amenity_id"] == "amenity-gym"
    assert ledger_filters["booking_status"] == "approved"


def test_refund_rpc_does_not_require_a_key_python_never_sends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refund carries the amount the RPC inserts.

    ``refund_amenity_deposit`` inserts ``p_payload ->> 'amount'``. The service
    sent no amount at all -- deliberately, because a refund whose size is a
    request parameter is a refund somebody can ask to be larger -- so every
    refund inserted NULL and the RPC's own ceiling check passed vacuously.

    The amount is still not the caller's to choose: it is ``remaining_refund``
    off ``amenity_ledger_overview``, the same aggregate the RPC checks against,
    read here from the ledger row the service already fetches.
    """
    captured: dict = {}

    def _capture(client, occurrence_id, payload):
        captured.update(payload)
        return "event-1"

    _patch_read_back(monkeypatch)
    monkeypatch.setattr(amenities_service.repo, "refund_deposit", _capture)

    amenities_service.refund_deposit(
        None,
        "u1",
        "occurrence-1",
        RefundDepositRequest(reason="Deposit returned", notes=None),
    )
    unsent = rpc_payload_keys("refund_amenity_deposit") - set(captured)
    assert "amount" not in unsent
    # ...and it is the ledger's figure, not a number off the screen.
    assert captured["amount"] == 500.00


def test_a_refund_with_nothing_left_is_refused_rather_than_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zero-amount refund event would be a lie in the ledger, so it is a 4xx.

    Before, this inserted a NULL-amount 'refund' onto a booking whose deposit
    had already been returned -- a transaction that reads as a refund and moves
    no money.
    """
    _patch_read_back(monkeypatch)
    monkeypatch.setattr(
        amenities_service.repo,
        "get_ledger_row",
        lambda client, community_id, occurrence_id: _ledger_row(
            remaining_refund="0.00"
        ),
    )

    def _must_not_run(client, occurrence_id, payload):  # pragma: no cover
        raise AssertionError("the refund RPC was called with nothing to refund")

    monkeypatch.setattr(amenities_service.repo, "refund_deposit", _must_not_run)

    with pytest.raises(ValidationError):
        amenities_service.refund_deposit(
            None,
            "u1",
            "occurrence-1",
            RefundDepositRequest(reason="Deposit returned", notes=None),
        )


# ---------------------------------------------------------------------------
# 5. D4 -- the report KPI keys the RPC returns are the keys Python reads
# ---------------------------------------------------------------------------
class _KeyRecordingTotals(dict):
    """A totals dict that records every key ``build_report`` asks it for."""

    def __init__(self) -> None:
        super().__init__()
        self.read: set[str] = set()

    def get(self, key, default=None):  # noqa: ANN001
        self.read.add(key)
        return super().get(key, default)


def test_report_kpi_keys_cover_what_build_report_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every KPI the report answers with was computed by the aggregate.

    ``build_report`` used to read total_amenities / total_active_bookings /
    pending_approvals / total_revenue / active_amenities / bookings_this_month
    off a document that returns total_bookings / approved_bookings /
    cancelled_bookings / total_charged / total_paid / total_refunded. Zero
    overlap, all six ``.get`` calls defaulting: the reports page rendered six
    hardcoded 0s that looked like measurements.

    The response KPIs are now one per RPC key. The four that named nothing the
    aggregate computes are gone from the response rather than zeroed -- a KPI
    with no source is a worse answer than no KPI.
    """
    totals = _KeyRecordingTotals()

    monkeypatch.setattr(
        amenities_service.repo,
        "fetch_report_totals",
        lambda client, community_id, payload: totals,
    )
    monkeypatch.setattr(
        amenities_service.repo, "list_ledger", lambda *args, **kwargs: ([], 0)
    )
    monkeypatch.setattr(
        amenities_service.repo, "list_amenities", lambda *args, **kwargs: ([], 0)
    )

    amenities_service.build_report(None, "u1")
    assert totals.read, "build_report read no KPI keys -- the recorder is broken"
    assert totals.read <= report_kpi_keys()
    # Every source key is used, not just a legal subset of them: a report that
    # quietly stopped reading `total_refunded` would still satisfy the subset.
    assert totals.read == report_kpi_keys()


# ---------------------------------------------------------------------------
# 6. D3 -- a block, as the database actually stores one, paints blocked
# ---------------------------------------------------------------------------
def test_a_block_as_stored_paints_blocked_on_the_timeline() -> None:
    """The timeline reads the booking TYPE, which is where 'blocked' lives.

    ``block_amenity_slot`` stores a block as status='approved' +
    booking_type='blocked' (0023 lines 1104-1105). ``_timeline_state`` keyed on
    ``stored_status == 'blocked'`` -- a value ``public.booking_status`` cannot
    hold -- so every admin block painted as an ordinary resident booking.
    """
    row = _booking_row(
        status="Approved",
        stored_status="approved",
        booking_type="blocked",
        source="admin",
        title="Deep clean",
        department="Cleaning",
        requested_by_membership_id=None,
        resident_name=None,
        unit_id=None,
        unit_code=None,
        tower=None,
    )
    assert amenities_service._timeline_state(row) == "blocked"


# ---------------------------------------------------------------------------
# 7. D4 -- the wire status is a lowercase machine value
# ---------------------------------------------------------------------------
def test_wire_status_is_a_lowercase_machine_value() -> None:
    """Title-case never crosses the wire.

    ``amenity_booking_overview.status`` is the enum rendered for a human --
    'Approved', 'No Show' (0023 lines 484-492) -- and ``_to_booking`` passed it
    through verbatim, so every case-sensitive comparison downstream missed.
    The status is derived from ``stored_status``, which is
    ``amenity_bookings.status::text`` and already the machine value.
    """
    booking = amenities_service._to_booking(
        _booking_row(status="Approved", stored_status="approved")
    )
    assert booking.status in {
        "pending",
        "approved",
        "confirmed",
        "rejected",
        "cancelled",
        "completed",
        "no_show",
    }
    assert booking.status == "approved"


def test_a_title_case_display_status_folds_to_its_machine_value() -> None:
    """The view's worst case: two words and a capital in each.

    'No Show' is the display rendering of the enum value ``no_show``; a caller
    handing us a row with only the display column still gets the machine value.
    """
    row = _booking_row(status="No Show", stored_status="no_show")
    assert amenities_service._to_booking(row).status == "no_show"

    view_only = _booking_row(status="No Show")
    view_only.pop("stored_status")
    assert amenities_service._to_booking(view_only).status == "no_show"


# ---------------------------------------------------------------------------
# 8. D2/D5 -- the only live amenity write model carries image and hours
# ---------------------------------------------------------------------------
def test_amenity_write_accepts_image_and_hours() -> None:
    """``AmenityWrite`` has a field for everything the catalogue form collects.

    It is the model behind POST/PUT ``/dashboard/amenities``, the only amenity
    write endpoints in the app, and it is ``extra='forbid'`` -- so a photo and
    an opening hour with no field here could not even be smuggled through as
    extra keys. They were silently unsendable.
    """
    names = set(AmenityWrite.model_fields)
    names.update(
        field.alias
        for field in AmenityWrite.model_fields.values()
        if field.alias is not None
    )
    # Accept camelCase spellings of the same fields as satisfying the contract.
    normalized = {
        re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower() for name in names
    }
    assert {"image", "opening_time", "closing_time"} <= normalized


# ---------------------------------------------------------------------------
# 9. D2 -- the snapshot projection carries image and hours on the legacy branch
# ---------------------------------------------------------------------------
def test_snapshot_amenity_projection_carries_image_and_hours() -> None:
    """The catalogue the frontend reads out of the snapshot can show both.

    The legacy branch is the live one in every environment, hosted and fresh,
    and it emitted no 'image' key and no 'openingTime' at all -- so however well
    the write path worked, the read could never show what it stored.
    """
    legacy_row = {
        "id": "a1",
        "name": "Clubhouse Gym",
        "description": "A bright first-floor gym.",
        "category": "Fitness",
        "location": "Ground Floor",
        "capacity": 24,
        "booking_mode": "shared",
        "approval_required": False,
        "hourly_rate": 0,
        "status": "active",
        "image_url": "https://images.example/gym.jpg",
        "opening_time": "06:00:00",
        "closing_time": "22:00:00",
        "created_at": "2026-07-01T06:00:00+00:00",
        "updated_at": "2026-07-01T06:00:00+00:00",
    }
    projected = dashboard_service._amenities([legacy_row], legacy=True)
    assert projected, "the projection returned nothing"
    item = projected[0]
    assert "image" in item
    assert item.get("openingTime")
    # The values, not just the keys -- and `description` is the amenity's own
    # column now, not a second copy of `category` under a different name.
    assert item["image"] == "https://images.example/gym.jpg"
    assert item["openingTime"] == "06:00:00"
    assert item["closingTime"] == "22:00:00"
    assert item["description"] == "A bright first-floor gym."
    assert item["category"] == "Fitness"


# ---------------------------------------------------------------------------
# 10. D2 -- what `AmenityWrite` will and will not accept in those new fields
#
# The image ships as a capped base64 data URL into the existing
# `amenities.image_url`: no storage bucket, because HomeBandhu has no
# deployment for one. The browser downscales before it submits and these
# validators are the backstop, so an oversized or malformed upload is a 422
# with a sentence in it rather than a Postgres error or a row nobody can load.
# ---------------------------------------------------------------------------
def _write(**overrides: object) -> AmenityWrite:
    payload: dict = {"name": "Clubhouse Gym"}
    payload.update(overrides)
    return AmenityWrite(**payload)


def test_an_https_image_url_is_accepted_and_an_http_one_is_not() -> None:
    assert _write(image="https://images.example/gym.jpg").image == (
        "https://images.example/gym.jpg"
    )
    with pytest.raises(PydanticValidationError):
        _write(image="http://images.example/gym.jpg")
    with pytest.raises(PydanticValidationError):
        _write(image="javascript:alert(1)")


def test_a_base64_image_data_url_is_accepted() -> None:
    """The shape the downscaler produces. Empty normalises to None -- 'no image'
    and 'the empty string' are the same answer and the column stores NULL."""
    tiny = "data:image/png;base64," + "iVBORw0KGgo="
    assert _write(image=tiny).image == tiny
    assert _write(image="").image is None
    assert _write(image="   ").image is None
    with pytest.raises(PydanticValidationError):
        _write(image="data:image/svg+xml;base64,PHN2Zz4=")


def test_an_oversized_inline_image_is_refused() -> None:
    """~100KB of binary is ~140_000 base64 characters. One character over and
    the request is a 422; the browser is expected to have downscaled already."""
    payload = "A" * 140_001
    with pytest.raises(PydanticValidationError):
        _write(image="data:image/png;base64," + payload)


def test_opening_hours_take_both_clock_spellings_and_nothing_else() -> None:
    """'HH:MM' is what an <input type="time"> emits; 'HH:MM:SS' is what Postgres
    hands back. Both are accepted so a value can round-trip unchanged."""
    assert _write(opening_time="06:00", closing_time="22:00:00").opening_time == "06:00"
    assert _write(opening_time="").opening_time is None
    for bad in ("6:00", "25:00", "06:60", "morning"):
        with pytest.raises(PydanticValidationError):
            _write(opening_time=bad)


def test_reversed_opening_hours_are_a_422_not_a_500() -> None:
    """`amenities_hours_check` (0023 line 121) refuses this in Postgres, which
    reaches the admin as a failed save with no explanation. Checked here, the
    same rule is a field error with a sentence in it."""
    with pytest.raises(PydanticValidationError):
        _write(opening_time="22:00", closing_time="06:00")
    with pytest.raises(PydanticValidationError):
        _write(opening_time="09:00", closing_time="09:00")
    # One-sided hours are legal -- the CHECK only fires when both are set.
    assert _write(opening_time="06:00").closing_time is None
    assert _write(closing_time="22:00").opening_time is None


# ---------------------------------------------------------------------------
# 11. D4 -- the report's status filter, in both directions
#
# The options the screen offers and the values the filter accepts are one list,
# and the column being filtered is the raw enum. All three have to agree or the
# filter is a dropdown whose entries return nothing.
# ---------------------------------------------------------------------------
def _report_with_status(monkeypatch: pytest.MonkeyPatch, status: str | None):
    ledger_filters: dict = {}

    def _capture_ledger(client, community_id, **kwargs):
        ledger_filters.update(kwargs)
        return [], 0

    monkeypatch.setattr(
        amenities_service.repo,
        "fetch_report_totals",
        lambda client, community_id, payload: {},
    )
    monkeypatch.setattr(amenities_service.repo, "list_ledger", _capture_ledger)
    monkeypatch.setattr(
        amenities_service.repo, "list_amenities", lambda *args, **kwargs: ([], 0)
    )

    report = amenities_service.build_report(None, "u1", booking_status=status)
    return report, ledger_filters


def test_the_report_status_options_are_all_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every option offered must select rows the ledger column can hold.

    'confirmed' and 'blocked' used to be offered and neither is a value
    ``booking_status`` can ever hold -- a block is an APPROVED row wearing
    ``booking_type = 'blocked'``. Two dropdown entries that always came back
    empty (issue #48 D4).
    """
    report, _ = _report_with_status(monkeypatch, None)
    offered = set(report.options.booking_statuses)

    assert "confirmed" not in offered
    assert "blocked" not in offered
    assert {
        booking_status_to_storage(option) for option in offered
    } <= booking_status_enum()


def test_the_report_status_filter_reaches_the_ledger_as_the_stored_word(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wire says 'pending'; the column holds 'requested'.

    ``amenity_ledger_overview.booking_status`` is ``amenity_bookings.status``
    as text, and the filter is a bare equality against it -- so the one option
    whose wire word differs from its stored word has to be translated on the
    way in, or it selects nothing at all.
    """
    _, filters = _report_with_status(monkeypatch, "pending")
    assert filters["booking_status"] == "requested"

    _, filters = _report_with_status(monkeypatch, "approved")
    assert filters["booking_status"] == "approved"

    # No filter stays no filter -- not a filter on the pending rows.
    _, filters = _report_with_status(monkeypatch, None)
    assert filters["booking_status"] is None


def test_an_unreachable_report_status_is_refused_rather_than_matching_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty table is indistinguishable from "you have none of those"."""
    with pytest.raises(ValidationError):
        _report_with_status(monkeypatch, "confirmed")
    with pytest.raises(ValidationError):
        _report_with_status(monkeypatch, "blocked")


def test_the_ledger_wire_status_is_the_wires_word_not_the_enums(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ledger view exposes the raw enum, so 'requested' arrives here and
    'pending' is what every other endpoint calls the same state."""
    transaction = amenities_service._to_transaction(
        _ledger_row(booking_status="requested"), []
    )
    assert transaction.booking_status == "pending"
