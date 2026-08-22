"""Address lookup, proxied to Nominatim under its usage policy.

**Why the backend proxies this at all.** The browser could call
``nominatim.openstreetmap.org`` directly and save a hop. It must not: the
policy that makes the service free asks for an identifying ``User-Agent`` (which
a browser will not let script set), an absolute ceiling of one request per
second *per application*, and caching of results. None of those three can be
honoured from inside a tab -- a thousand tabs are a thousand uncoordinated
callers -- and all three can be honoured here, once, for everybody.

The three obligations, and where each is discharged:

* **Identify yourself** -- :data:`_USER_AGENT`, sent on every upstream request.
* **At most one request per second** -- :func:`_fetch` holds a lock across the
  whole upstream call and sleeps out the remainder of the last second before
  starting. Holding the lock across the request is single-flight as well as
  throttling: two callers searching different things queue, rather than both
  reaching the upstream inside one tick.
* **Cache** -- :data:`_CACHE`, a bounded TTL map. Address text is typed by
  people and repeats heavily (a hundred servicemen registering in one suburb
  search the same three strings), so this is not a micro-optimisation, it is
  most of the compliance.

**No API key, and nothing configurable.** There is no setting to point this at
another host, because a proxy with a caller-controlled destination is a
server-side request forgery with a docstring. The host is a constant below.

Failures are :class:`ServiceUnavailableError`, never 500. A timeout or a 429
from the upstream is a true statement about a third party -- the picker says
"address search is busy, drop the pin instead" and stays usable, which a 500
would not.
"""

from __future__ import annotations

import asyncio
import time
import weakref
from typing import Any

import httpx

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger
from app.domain.geo_schemas import LOCATION_LABEL_MAX_LENGTH, GeoPlace

_logger = get_logger(__name__)

_BASE_URL = "https://nominatim.openstreetmap.org"

#: Nominatim's policy asks for an identifying agent with a contact route. The
#: repository is the contact route this project has.
_USER_AGENT = "HomeBandhu/1.0 (student project; https://github.com/painful-bug/MAY2026-Team-035)"

#: One second is the documented absolute maximum rate. This is that number, not
#: a comfortable margin under it, because the sleep only ever runs when two
#: searches land inside the same second -- which caching makes rare.
_MIN_INTERVAL_SECONDS = 1.0

#: Short. The caller is a person waiting with a text box open; twelve seconds of
#: spinner is worse for them than "try again", and the upstream is a courtesy
#: service with no availability promise.
_TIMEOUT_SECONDS = 6.0

#: A day. Addresses do not move, and the entry that matters -- the suburb a
#: hundred people type -- is worth keeping for exactly as long as the shift that
#: types it.
_CACHE_TTL_SECONDS = 24 * 60 * 60

#: Bounded because this is a process-lifetime dictionary keyed by user input.
#: Oldest-inserted is evicted first: a cache of the last thousand distinct
#: searches is all the hit rate there is to win.
_CACHE_MAX_ENTRIES = 1_000

_SEARCH_LIMIT = 5

#: ``(kind, key) -> (stored_at, payload)``. ``dict`` preserves insertion order,
#: which is the whole eviction policy.
_CACHE: dict[tuple[str, str], tuple[float, Any]] = {}

# One lock per event loop rather than one module-level lock. ``asyncio.Lock``
# binds to the first loop that awaits it and refuses every other one, and the
# test suite stands up a fresh ``TestClient`` -- and therefore a fresh loop --
# per test. The *throttle* is still process-wide, because the timestamp it
# compares against is: production runs one loop and one entry lives here.
_LOCKS: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = (
    weakref.WeakKeyDictionary()
)
#: ``-inf`` rather than ``0.0`` so the very first call never waits: ``monotonic``
#: is measured from an arbitrary epoch, and on a platform where that epoch is
#: near zero the first search of the process would sleep for no reason.
_last_request_at = float("-inf")


def _lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[loop] = lock
    return lock


def _build_client() -> httpx.AsyncClient:
    """The outbound client. A function so tests can substitute a transport.

    Constructed per call rather than shared: this module makes a handful of
    requests a minute at most, and a long-lived client would have to be bound to
    an event loop and torn down with the app for no measurable gain.
    """
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        timeout=_TIMEOUT_SECONDS,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        follow_redirects=False,
    )


def reset_cache() -> None:
    """Empty the cache and the throttle clock. For tests only."""
    global _last_request_at
    _CACHE.clear()
    _last_request_at = float("-inf")


def _cache_get(kind: str, key: str) -> Any | None:
    entry = _CACHE.get((kind, key))
    if entry is None:
        return None
    stored_at, payload = entry
    if time.monotonic() - stored_at > _CACHE_TTL_SECONDS:
        _CACHE.pop((kind, key), None)
        return None
    return payload


def _cache_put(kind: str, key: str, payload: Any) -> None:
    _CACHE[(kind, key)] = (time.monotonic(), payload)
    while len(_CACHE) > _CACHE_MAX_ENTRIES:
        _CACHE.pop(next(iter(_CACHE)))


def _unavailable() -> ServiceUnavailableError:
    """One message and one code for every upstream failure.

    The caller is told what to do instead rather than what went wrong: whether
    the timeout was ours or a 429 was theirs changes nothing a person in a
    registration form can act on, and the map pin is right there.
    """
    return ServiceUnavailableError(
        "Address search is busy right now. Drop the pin on the map instead.",
        code="geocoding_unavailable",
    )


async def _fetch(path: str, params: dict[str, Any]) -> Any:
    """One upstream call, rate-limited to at most one per second, process-wide.

    The lock is held across the request, not merely across the timestamp update.
    That makes concurrent callers queue behind one another instead of all
    clearing the same "a second has passed" check at once -- which is the only
    version of this that actually respects the ceiling under load.
    """
    global _last_request_at
    async with _lock():
        elapsed = time.monotonic() - _last_request_at
        if elapsed < _MIN_INTERVAL_SECONDS:
            await asyncio.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        _last_request_at = time.monotonic()
        try:
            async with _build_client() as client:
                response = await client.get(path, params=params)
        except httpx.HTTPError as exc:
            _logger.warning("Nominatim %s failed: %s", path, exc)
            raise _unavailable() from exc

    if response.status_code in (429, 503):
        _logger.warning("Nominatim %s throttled us: %s", path, response.status_code)
        raise _unavailable()
    if response.status_code >= 400:
        _logger.warning("Nominatim %s answered %s", path, response.status_code)
        raise _unavailable()
    try:
        return response.json()
    except ValueError as exc:
        _logger.warning("Nominatim %s returned a non-JSON body", path)
        raise _unavailable() from exc


#: The address keys worth putting in a short label, most specific first. Chosen
#: rather than taking the first three of ``display_name``: that string starts
#: with a house number as often as not, and a house number is precisely the part
#: this label exists to leave out.
_LOCALITY_KEYS = (
    "neighbourhood",
    "suburb",
    "village",
    "town",
    "city_district",
    "hamlet",
)
_CITY_KEYS = ("city", "town", "municipality", "county", "state_district")
_REGION_KEYS = ("state", "region")


def _first(address: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = address.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _label_from(row: dict[str, Any]) -> str:
    """A three-part, human-sized label: locality, city, state.

    Falls back to the leading parts of ``display_name`` when the upstream sent
    no ``address`` object, and to the whole line when even that is missing --
    an ugly label beats an empty field the person then has to invent.
    """
    address = row.get("address")
    parts: list[str] = []
    if isinstance(address, dict):
        for keys in (_LOCALITY_KEYS, _CITY_KEYS, _REGION_KEYS):
            part = _first(address, keys)
            if part and part not in parts:
                parts.append(part)
    if not parts:
        display = str(row.get("display_name") or "").strip()
        parts = [piece.strip() for piece in display.split(",")[:3] if piece.strip()]
    label = ", ".join(parts)
    return label[:LOCATION_LABEL_MAX_LENGTH].strip()


def _to_place(row: dict[str, Any]) -> GeoPlace | None:
    """One upstream row, or ``None`` when it carries no usable coordinate."""
    try:
        latitude = float(row["lat"])
        longitude = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    label = _label_from(row)
    if not label:
        return None
    return GeoPlace(
        label=label,
        # 200 characters is roughly the longest genuine `display_name`; the cap
        # is here so a pathological upstream row cannot become the response.
        description=str(row.get("display_name") or label)[:200].strip(),
        latitude=latitude,
        longitude=longitude,
    )


async def search(query: str) -> list[GeoPlace]:
    """Up to five places matching a typed address.

    **Called on an explicit search, never per keystroke.** The usage policy
    forbids autocomplete against this service in as many words, which is why the
    picker has a Search button and no type-ahead. The cache key is the
    normalised query, so the third person to search "andheri west" today costs
    the upstream nothing.
    """
    key = " ".join(query.lower().split())
    if not key:
        return []
    cached = _cache_get("search", key)
    if cached is not None:
        return list(cached)

    payload = await _fetch(
        "/search",
        {
            "q": key,
            "format": "jsonv2",
            "limit": _SEARCH_LIMIT,
            "addressdetails": 1,
        },
    )
    rows = payload if isinstance(payload, list) else []
    places = [
        place
        for place in (_to_place(row) for row in rows if isinstance(row, dict))
        if place is not None
    ]
    _cache_put("search", key, places)
    return list(places)


async def reverse(latitude: float, longitude: float) -> GeoPlace:
    """The label for a dropped pin.

    Rounded to five decimal places -- about a metre -- before it becomes a cache
    key, because dragging a pin emits a stream of coordinates that differ in the
    ninth decimal and mean the same doorstep. Without the rounding the cache
    would never hit on exactly the operation that generates the most lookups.
    """
    key = f"{round(latitude, 5)},{round(longitude, 5)}"
    cached = _cache_get("reverse", key)
    if cached is not None:
        return cached

    payload = await _fetch(
        "/reverse",
        {
            "lat": round(latitude, 5),
            "lon": round(longitude, 5),
            "format": "jsonv2",
            "addressdetails": 1,
            # 14 is roughly suburb level. Asking for the building would give a
            # label more precise than the field is allowed to be.
            "zoom": 14,
        },
    )
    place = _to_place(payload) if isinstance(payload, dict) else None
    if place is None:
        raise NotFoundError(
            "No address was found at that point.", code="geo_place_not_found"
        )
    _cache_put("reverse", key, place)
    return place
