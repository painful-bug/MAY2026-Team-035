from app.domain.schemas import AmenityWrite
from app.services.dashboard_service import _amenities


def test_dashboard_amenity_keeps_image_and_bookable_hours() -> None:
    payload = AmenityWrite(
        name="Badminton Court",
        image="data:image/png;base64,AA==",
        opening_time="06:00",
        closing_time="22:00",
    ).model_dump(exclude_none=True)

    assert payload["image"] == "data:image/png;base64,AA=="
    assert payload["opening_time"] == "06:00"
    assert payload["closing_time"] == "22:00"

    amenity = _amenities(
        [
            {
                "id": "amenity-1",
                "name": "Badminton Court",
                "description": "Court",
                "image_url": payload["image"],
                "capacity": 10,
                "opening_time": payload["opening_time"],
                "closing_time": payload["closing_time"],
                "booking_rules": {},
                "is_active": True,
            }
        ],
        legacy=False,
    )[0]

    assert amenity["image"] == payload["image"]
    assert amenity["openingTime"] == "06:00"
    assert amenity["closingTime"] == "22:00"
    assert amenity["capacity"] == 10
