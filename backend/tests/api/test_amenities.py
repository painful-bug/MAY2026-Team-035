"""Amenity-booking API cases."""

import pytest
from fastapi.testclient import TestClient

from app.domain.amenity_schemas import CancelBookingRequest


def test_api_007_partial_booking_cancellation_returns_cancelled_day_count(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import amenities as amenities_router

    endpoint = "POST /api/v1/amenity-bookings/cancel"
    input_data = {
        "occurrenceIds": ["booking-day-1", "booking-day-3"],
        "reasonCode": "schedule_change",
        "reason": "Only selected dates should be cancelled.",
    }
    expected_output = {
        "status_code": 200,
        "body": {"message": "2 booking day(s) cancelled."},
    }
    captured_input: dict[str, object] = {}

    def cancel_selected_days(_: object, request: CancelBookingRequest) -> int:
        captured_input.update(request.model_dump(mode="json", by_alias=True))
        return 2

    monkeypatch.setattr(
        amenities_router.amenities_service,
        "cancel_bookings",
        cancel_selected_days,
    )

    response = resident_api_client.post(
        "/api/v1/amenity-bookings/cancel",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/amenity-bookings/cancel"
    assert captured_input == input_data
    assert actual_output == expected_output


def test_api_008_booking_cancellation_rejects_empty_date_selection(
    resident_api_client: TestClient,
    csrf_headers: dict[str, str],
) -> None:
    endpoint = "POST /api/v1/amenity-bookings/cancel"
    input_data = {"occurrenceIds": [], "reasonCode": "schedule_change"}
    expected_output = {
        "status_code": 422,
        "error_code": "request_validation_error",
    }

    response = resident_api_client.post(
        "/api/v1/amenity-bookings/cancel",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/amenity-bookings/cancel"
    assert actual_output["status_code"] == expected_output["status_code"]
    assert actual_output["body"]["error"]["code"] == expected_output["error_code"]
