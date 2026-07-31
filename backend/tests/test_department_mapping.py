"""The department wire/storage seams.

Three of them, and each one is a place where a silent mistranslation would be
invisible until a user noticed the wrong thing on screen:

* ``Active``/``Inactive`` vs the stored ``active``/``archived`` (A6),
* Postgres ``time`` vs the ``HH:MM`` an ``<input type="time">`` accepts,
* the jsonb patch the RPC reads, where a *missing* key and a ``null`` value mean
  opposite things.
"""

from __future__ import annotations

import pytest

from app.core.formatting import clock_time
from app.domain.department_schemas import StaffMemberInput, UpdateDepartmentRequest
from app.domain.vocabularies import (
    department_status_to_storage,
    department_status_to_wire,
)
from app.services.departments_service import _staff_payload


@pytest.mark.parametrize(
    ("stored", "expected"),
    [("active", "Active"), ("archived", "Inactive")],
)
def test_department_status_to_wire(stored, expected):
    assert department_status_to_wire(stored) == expected


@pytest.mark.parametrize(
    ("wire", "expected"),
    [
        ("Active", "active"),
        ("Inactive", "archived"),
        ("  inactive ", "archived"),
        # The stored spelling is accepted too, so a caller echoing a value back
        # is not punished for it.
        ("archived", "archived"),
    ],
)
def test_department_status_to_storage(wire, expected):
    assert department_status_to_storage(wire) == expected


def test_unknown_department_status_is_rejected_not_guessed():
    assert department_status_to_storage("Deleted") is None
    assert department_status_to_storage("") is None
    assert department_status_to_storage(None) is None


def test_department_status_round_trips_both_ways():
    """Unlike the complaint statuses, this mapping is a true bijection."""
    for wire in ("Active", "Inactive"):
        assert department_status_to_wire(department_status_to_storage(wire)) == wire
    for stored in ("active", "archived"):
        assert department_status_to_storage(department_status_to_wire(stored)) == stored


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("08:00:00", "08:00"),
        ("23:59:00", "23:59"),
        ("00:00:00", "00:00"),
        # Postgres can include fractional seconds.
        ("07:30:00.000000", "07:30"),
        ("9:05:00", "09:05"),
        (None, None),
        ("", None),
        ("garbage", None),
    ],
)
def test_clock_time(value, expected):
    assert clock_time(value) == expected


def test_staff_payload_omits_untouched_fields():
    """A key the caller never sent must not appear in the patch.

    The RPC treats key presence as "change this", so including ``phone: null``
    for a member whose phone was never mentioned would erase a stored number.
    """
    member = StaffMemberInput(name="  Ramesh Kumar  ")
    assert _staff_payload([member]) == [{"name": "Ramesh Kumar"}]


def test_staff_payload_keeps_an_explicit_null():
    """An explicit null is a request to clear, and must survive."""
    member = StaffMemberInput.model_validate({"name": "Mohan Das", "phone": None})
    assert _staff_payload([member]) == [{"name": "Mohan Das", "phone": None}]


def test_staff_payload_carries_the_id_that_makes_it_an_update():
    member = StaffMemberInput.model_validate(
        {"id": "abc", "name": "Arun Singh", "role": "Technician"}
    )
    assert _staff_payload([member]) == [
        {"id": "abc", "name": "Arun Singh", "role": "Technician"}
    ]


def test_blank_staff_id_is_not_an_id():
    """The create form seeds ``id: ''``; sending it would look like an update."""
    member = StaffMemberInput.model_validate({"id": "", "name": "New Hire"})
    assert member.id is None
    assert "id" not in _staff_payload([member])[0]


def test_update_request_distinguishes_omitted_from_null():
    """The whole partial-update contract rests on this."""
    omitted = UpdateDepartmentRequest.model_validate({"name": "Security Operations"})
    assert "description" not in omitted.model_dump(exclude_unset=True)

    cleared = UpdateDepartmentRequest.model_validate(
        {"name": "Security Operations", "description": None}
    )
    assert "description" in cleared.model_dump(exclude_unset=True)


def test_operating_hours_rejects_a_non_clock_string():
    """A bad time must fail at the edge, not become a null column silently."""
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        UpdateDepartmentRequest.model_validate({"operatingHours": {"start": "8am"}})

    ok = UpdateDepartmentRequest.model_validate({"operatingHours": {"start": "08:00"}})
    assert ok.operating_hours is not None
    assert ok.operating_hours.start == "08:00"
