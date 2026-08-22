"""The location picker's address proxy.

Four things are tested, and only the first is about geocoding.

**That the upstream's payload never reaches the client.** Nominatim answers with
about thirty fields per result. Three cross this boundary. A test that asserted
"the response has a label" would pass on a handler that forwarded the lot, so
the assertions here are on the *exact* key set.

**That the usage policy is honoured**, because that is the only reason this
endpoint exists rather than a `fetch` in the browser: an identifying
`User-Agent`, one request per second, and a cache. All three are asserted from
the outside -- what the upstream *received*, and how often -- rather than by
reading module state, so an implementation that keeps the constants and stops
applying them fails.

**That an upstream failure is a 503 and not a 500.** The picker keeps working
without address search; the map pin is right there. A 500 would tell the client
that the request was wrong when it was not.

**That the guard is identity-only.** A service person registering and a founder
onboarding a community both need this and neither holds a membership yet, so a
membership guard creeping onto these routes would 403 exactly the callers the
feature exists for. The fixture therefore overrides identity alone.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.domain.schemas import Principal
from app.services import geocoding_service

SEARCH = "/api/v1/geo/search"
REVERSE = "/api/v1/geo/reverse"

#: One ``/search`` row as Nominatim actually answers with ``format=jsonv2`` and
#: ``addressdetails=1`` -- trimmed of the fields nobody reads, but with the
#: shape and the noise intact, because the point of the response test is that
#: the noise does not come out the other side.
ANDHERI: dict[str, Any] = {
    "place_id": 240_186_123,
    "licence": "Data © OpenStreetMap contributors, ODbL 1.0.",
    "osm_type": "relation",
    "osm_id": 7_951_637,
    "lat": "19.1364",
    "lon": "72.8296",
    "category": "boundary",
    "type": "administrative",
    "place_rank": 20,
    "importance": 0.42,
    "addresstype": "suburb",
    "name": "Andheri West",
    "display_name": (
        "Andheri West, Mumbai, Mumbai Suburban, Maharashtra, 400053, India"
    ),
    "address": {
        "suburb": "Andheri West",
        "city": "Mumbai",
        "county": "Mumbai Suburban",
        "state": "Maharashtra",
        "postcode": "400053",
        "country": "India",
        "country_code": "in",
    },
    "boundingbox": ["19.09", "19.17", "72.80", "72.87"],
}


@pytest.fixture(autouse=True)
def clean_geocoder() -> Generator[None, None, None]:
    """No cache and no throttle debt carried between tests.

    Both are module-level and deliberately process-wide -- that is what makes
    the rate limit mean anything with more than one worker request in flight --
    so without this the second test to search "andheri west" would assert
    against the first test's cache entry.
    """
    geocoding_service.reset_cache()
    yield
    geocoding_service.reset_cache()


@pytest.fixture
def geo_client(api_client: TestClient) -> TestClient:
    """A signed-in caller with **no membership override**.

    Deliberately not ``resident_api_client``: a membership guard added to these
    routes has to fail a test rather than pass one.
    """
    api_client.app.dependency_overrides[get_current_user] = lambda: Principal(
        user_id="picker-profile-id",
        email="ravi@example.com",
        email_verified=True,
        full_name="Ravi Kumar",
    )
    return api_client


class Upstream:
    """A stand-in Nominatim. Records every request it is asked to answer."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.times: list[float] = []
        self.responses: list[Any] = []

    def stage(self, *responses: Any) -> None:
        """Queue answers. The last one repeats once the queue runs dry."""
        self.responses = list(responses)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.times.append(time.monotonic())
        answer = (
            self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        )
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def upstream(monkeypatch: pytest.MonkeyPatch) -> Upstream:
    """Replace the outbound client's transport, not the service's functions.

    The throttle, the cache, the label builder and the error translation all
    live between the route and this transport, so mocking here is what keeps
    them under test instead of mocked away.
    """
    recorder = Upstream()
    recorder.stage(httpx.Response(200, json=[ANDHERI]))

    def fake_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://nominatim.openstreetmap.org",
            headers={
                "User-Agent": geocoding_service._USER_AGENT,
                "Accept": "application/json",
            },
            transport=httpx.MockTransport(recorder.handle),
        )

    monkeypatch.setattr(geocoding_service, "_build_client", fake_client)
    return recorder


def test_api_320_a_search_returns_three_fields_and_not_the_upstreams_payload(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """Thirty fields go in and four come out. Asserted as an exact key set,
    because "it has a label" would also pass on a handler that forwarded the
    licence string, the OSM id and the bounding box."""
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "andheri west"}
    expected_output = {
        "status_code": 200,
        "count": 1,
        "keys": ["description", "label", "latitude", "longitude"],
        "label": "Andheri West, Mumbai, Maharashtra",
        "latitude": 19.1364,
        "longitude": 72.8296,
    }

    response = geo_client.get(SEARCH, params=input_data)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "count": len(body),
        "keys": sorted(body[0]),
        "label": body[0]["label"],
        "latitude": body[0]["latitude"],
        "longitude": body[0]["longitude"],
    }

    assert actual_output == expected_output, endpoint


def test_api_321_the_upstream_call_identifies_itself_and_asks_for_five_results(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """Nominatim's usage policy asks for an identifying `User-Agent`, which a
    browser will not let script set -- so this endpoint existing at all is only
    justified while it sends one."""
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "andheri west"}
    expected_output = {
        "status_code": 200,
        "path": "/search",
        "limit": "5",
        "addressdetails": "1",
        "identifies_itself": True,
    }

    response = geo_client.get(SEARCH, params=input_data)
    sent = upstream.requests[0]
    actual_output = {
        "status_code": response.status_code,
        "path": sent.url.path,
        "limit": sent.url.params.get("limit"),
        "addressdetails": sent.url.params.get("addressdetails"),
        "identifies_itself": sent.headers.get("User-Agent", "").startswith(
            "HomeBandhu/"
        ),
    }

    assert actual_output == expected_output, endpoint


def test_api_322_the_same_search_twice_reaches_the_upstream_once(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """Caching is a term of use, not an optimisation: a hundred servicemen
    registering in one suburb type the same three strings. Case and spacing are
    normalised before the key, so "Andheri  West" is the same question."""
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "andheri west"}
    expected_output = {"status_codes": [200, 200], "upstream_calls": 1, "same": True}

    first = geo_client.get(SEARCH, params=input_data)
    second = geo_client.get(SEARCH, params={"q": "  Andheri   West  "})
    actual_output = {
        "status_codes": [first.status_code, second.status_code],
        "upstream_calls": len(upstream.requests),
        "same": first.json() == second.json(),
    }

    assert actual_output == expected_output, endpoint


def test_api_323_two_different_searches_are_spaced_out_by_the_throttle(
    geo_client: TestClient, upstream: Upstream, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One request per second is the documented absolute maximum, and the cache
    cannot help two people searching different things. The interval is shortened
    here so the assertion is about the mechanism rather than about waiting."""
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "two distinct searches"}
    monkeypatch.setattr(geocoding_service, "_MIN_INTERVAL_SECONDS", 0.25)
    expected_output = {"upstream_calls": 2, "spaced_out": True}

    geo_client.get(SEARCH, params={"q": "andheri west"})
    geo_client.get(SEARCH, params={"q": "bandra east"})
    actual_output = {
        "upstream_calls": len(upstream.requests),
        "spaced_out": (upstream.times[1] - upstream.times[0]) >= 0.25,
    }

    assert actual_output == expected_output, f"{endpoint} {input_data}"


def test_api_324_an_upstream_429_is_a_503_the_picker_can_act_on(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """Being throttled by somebody else's free service is a true statement about
    a third party, not a broken request. The screen still has a map pin, so the
    message says to use it."""
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "andheri west"}
    expected_output = {"status_code": 503, "code": "geocoding_unavailable"}

    upstream.stage(httpx.Response(429, text="Too Many Requests"))
    response = geo_client.get(SEARCH, params=input_data)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_325_an_upstream_timeout_is_a_503_and_is_not_cached(
    geo_client: TestClient, upstream: Upstream, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure must not poison the cache for a day. The retry after a timeout
    is the whole recovery path, and a cached error would remove it.

    The throttle interval is shortened because the retry is genuinely subject to
    it -- a failed attempt still spent the second -- and a test that proved that
    by waiting would cost the suite a second to say what `test_api_323` already
    says.
    """
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "andheri west"}
    monkeypatch.setattr(geocoding_service, "_MIN_INTERVAL_SECONDS", 0.01)
    expected_output = {
        "first_status": 503,
        "second_status": 200,
        "upstream_calls": 2,
    }

    upstream.stage(
        httpx.ConnectTimeout("nominatim did not answer"),
        httpx.Response(200, json=[ANDHERI]),
    )
    first = geo_client.get(SEARCH, params=input_data)
    second = geo_client.get(SEARCH, params=input_data)
    actual_output = {
        "first_status": first.status_code,
        "second_status": second.status_code,
        "upstream_calls": len(upstream.requests),
    }

    assert actual_output == expected_output, endpoint


def test_api_326_no_match_is_an_empty_list_and_not_a_404(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """"Nothing found -- drop the pin instead" is a state the pick-list renders.
    A 404 would send the client down the branch that means the route is gone."""
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "qqqqzzzz nowhere"}
    expected_output = {"status_code": 200, "body": []}

    upstream.stage(httpx.Response(200, json=[]))
    response = geo_client.get(SEARCH, params=input_data)
    actual_output = {"status_code": response.status_code, "body": response.json()}

    assert actual_output == expected_output, endpoint


def test_api_327_a_one_character_query_is_refused_before_the_upstream_is_touched(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """A one-character search matches most of the planet and would spend the
    one-per-second budget on nothing."""
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "a"}
    expected_output = {"status_code": 422, "upstream_calls": 0}

    response = geo_client.get(SEARCH, params=input_data)
    actual_output = {
        "status_code": response.status_code,
        "upstream_calls": len(upstream.requests),
    }

    assert actual_output == expected_output, endpoint


def test_api_328_an_unauthenticated_caller_is_refused(
    api_client: TestClient, upstream: Upstream
) -> None:
    """The guard is identity-only, which is a narrowing and not an absence: this
    proxies a third party's free service under our name, and an open one would
    be a rate limit anybody could exhaust for everybody."""
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "andheri west"}
    expected_output = {"status_code": 401, "upstream_calls": 0}

    response = api_client.get(SEARCH, params=input_data)
    actual_output = {
        "status_code": response.status_code,
        "upstream_calls": len(upstream.requests),
    }

    assert actual_output == expected_output, endpoint


def test_api_329_a_reverse_lookup_names_the_dropped_pin(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """The label is built from the address parts rather than from the head of
    `display_name`, which starts with a house number as often as not -- and the
    house number is exactly what this field must not carry."""
    endpoint = "GET /api/v1/geo/reverse"
    input_data = {"lat": 19.1364, "lon": 72.8296}
    expected_output = {
        "status_code": 200,
        "label": "Andheri West, Mumbai, Maharashtra",
        "latitude": 19.1364,
        "path": "/reverse",
    }

    upstream.stage(httpx.Response(200, json=ANDHERI))
    response = geo_client.get(REVERSE, params=input_data)
    body = response.json()
    actual_output = {
        "status_code": response.status_code,
        "label": body["label"],
        "latitude": body["latitude"],
        "path": upstream.requests[0].url.path,
    }

    assert actual_output == expected_output, endpoint


def test_api_330_a_point_with_no_address_is_a_404(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """Open sea. The client keeps the coordinate the person chose and leaves the
    label for them to write; nothing about the pin is invalid."""
    endpoint = "GET /api/v1/geo/reverse"
    input_data = {"lat": 0, "lon": 0}
    expected_output = {"status_code": 404, "code": "geo_place_not_found"}

    upstream.stage(httpx.Response(200, json={"error": "Unable to geocode"}))
    response = geo_client.get(REVERSE, params=input_data)
    actual_output = {
        "status_code": response.status_code,
        "code": response.json()["error"]["code"],
    }

    assert actual_output == expected_output, endpoint


def test_api_331_an_out_of_range_latitude_is_refused(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """Clamped at the route rather than passed through: this is the one place a
    caller can put an arbitrary value into an outbound URL."""
    endpoint = "GET /api/v1/geo/reverse"
    input_data = {"lat": 200, "lon": 0}
    expected_output = {"status_code": 422, "upstream_calls": 0}

    response = geo_client.get(REVERSE, params=input_data)
    actual_output = {
        "status_code": response.status_code,
        "upstream_calls": len(upstream.requests),
    }

    assert actual_output == expected_output, endpoint


def test_api_332_a_label_is_capped_at_the_length_the_column_accepts(
    geo_client: TestClient, upstream: Upstream
) -> None:
    """The database check is 120 characters. A label this API emits that could
    not then be saved is not a label, it is a form the person has to retype."""
    endpoint = "GET /api/v1/geo/search"
    input_data = {"q": "somewhere with a very long name"}
    expected_output = {"status_code": 200, "within_cap": True}

    upstream.stage(
        httpx.Response(
            200,
            json=[
                {
                    **ANDHERI,
                    "address": {
                        "suburb": "S" * 90,
                        "city": "C" * 90,
                        "state": "T" * 90,
                    },
                }
            ],
        )
    )
    response = geo_client.get(SEARCH, params=input_data)
    actual_output = {
        "status_code": response.status_code,
        "within_cap": len(response.json()[0]["label"]) <= 120,
    }

    assert actual_output == expected_output, endpoint
