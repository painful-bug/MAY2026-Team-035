"""Address search and reverse geocoding, for the location picker.

Two reads, and the reason they are server-side rather than a ``fetch`` from the
browser is written out in ``app/services/geocoding_service``: Nominatim's usage
policy asks for an identifying ``User-Agent``, one request per second per
application, and caching, and a tab can honour none of the three.

**Authenticated, no membership.** Every surface that picks a location -- a
service person registering, a founder onboarding a community, an admin fixing a
society's pin -- is behind sign-in, and two of the three hold no membership at
the moment they need it. So the guard here is the one from
``service_providers.py``: identity and nothing more.

**No CSRF dependency**, because both routes are ``GET``. ``require_csrf_unsafe``
would be a no-op on them; leaving it off says so rather than implying a write
surface that is not here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.domain.geo_schemas import GeoPlace
from app.domain.schemas import Principal
from app.services import geocoding_service

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get(
    "/search",
    response_model=list[GeoPlace],
    summary="Find a place by typing its address",
)
async def search_places(
    query: str = Query(
        ...,
        alias="q",
        min_length=3,
        max_length=120,
        description=(
            "The address text a person typed. Three characters minimum: a "
            "shorter query matches most of the planet and spends the upstream's "
            "one-per-second budget on nothing."
        ),
    ),
    _: Principal = Depends(get_current_user),
) -> list[GeoPlace]:
    """Up to five places matching the typed address, best match first.

    **Called on an explicit search, never per keystroke.** The upstream's usage
    policy forbids autocomplete against it in as many words, which is why the
    picker has a Search button and no type-ahead. Treat this as a button, not as
    an input event.

    An empty list is a 200, not a 404: "no match" is an answer the pick-list
    renders ("nothing found -- drop the pin instead"), and a 404 would push it
    down the error branch that means the route is missing.

    | Status | Code | Cause |
    |---|---|---|
    | 401 | `authentication_error` | No credentials |
    | 422 | `request_validation_error` | `q` shorter than 3 or longer than 120 |
    | 503 | `geocoding_unavailable` | The upstream timed out, refused, or throttled us |
    """
    return await geocoding_service.search(query)


@router.get(
    "/reverse",
    response_model=GeoPlace,
    summary="Name the point a pin was dropped on",
)
async def reverse_place(
    latitude: float = Query(..., alias="lat", ge=-90, le=90),
    longitude: float = Query(..., alias="lon", ge=-180, le=180),
    _: Principal = Depends(get_current_user),
) -> GeoPlace:
    """The suggested label for a coordinate the person chose on the map.

    Answers at roughly suburb precision rather than building precision. That is
    a deliberate ceiling, not a limitation of the upstream: the label is stored
    on the profile and shown to hiring managers, and "Andheri West, Mumbai" is
    the coarse fact the person offered. A street address would be a different
    disclosure wearing the same field name.

    **404 over the sea.** A point with no address is not an error in the
    request; the picker keeps the coordinate and leaves the label for the person
    to write.

    | Status | Code | Cause |
    |---|---|---|
    | 401 | `authentication_error` | No credentials |
    | 404 | `geo_place_not_found` | Nothing is addressable at that point |
    | 422 | `request_validation_error` | `lat`/`lon` missing or out of range |
    | 503 | `geocoding_unavailable` | The upstream timed out, refused, or throttled us |
    """
    return await geocoding_service.reverse(latitude, longitude)
