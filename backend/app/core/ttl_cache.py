"""A small, bounded, single-flight TTL cache for community-scoped reference reads.

Extracted from the pattern ``geocoding_service`` proved out first: a bounded
``dict`` keyed by whatever the caller chooses, a monotonic timestamp per entry,
oldest-inserted eviction once the map grows past a cap, and one loader call per
key even when several requests miss at the same instant.

**Why per-process, and why that is fine here.** This cache lives in one
worker's memory, the same way ``core.realtime``'s SSE hub is process-local
(``docs/ARCHITECTURE.md:180-183``): every uvicorn worker polls, caches and
evicts independently. Two workers can therefore disagree about a
community's departments, skills or settings for up to one TTL window after a
write lands on a different worker than the one a reader hits next. That is the
same trade-off the realtime hub already accepts, made for the same reason --
a shared cache would need a coordination layer (Redis, memcached, Postgres
``LISTEN``) this project has no other use for yet. Two things keep the window
small: the TTL is **60 seconds**, not the geocoding cache's one day, and every
mutation that changes a cached dataset invalidates that key **in the worker
that handled the write**, so the common case (one worker, or a write and the
next read landing on the same one) sees the change immediately regardless of
the TTL.

**Single-flight, not just memoized.** A cache miss takes a per-key lock before
calling ``loader``, so a herd of requests arriving together for the same
key -- the departments screen and a poll both landing inside the same second --
run the underlying read once, not once each. Different keys never block each
other: the lock is per-key, not global, which is deliberately different from
``geocoding_service``'s single asyncio lock (that one *has* to serialize every
request, because the thing it protects is an external rate limit, not just a
cache miss).

**Why this is not a drop-in replacement for ``geocoding_service``'s cache.**
That module is async (``asyncio.Lock``, bound to the running event loop) and
its lock's job is throttling calls to a third party to one a second --
the cache is incidental to that, not the point of it. Every reader in this
codebase that would use *this* utility is a synchronous ``def`` route running
in FastAPI's thread pool, so this cache uses ``threading.Lock`` throughout.
Forcing one lock type to serve both would either make the geocoding throttle
share a lock with unrelated cache misses (wrong) or make this cache pay for an
event loop it does not have (impossible outside one). They stay separate
utilities with a shared shape.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Generic, Hashable, TypeVar

T = TypeVar("T")

#: Distinguishes "no entry" from "an entry whose value is None" in the store.
_MISSING = object()


class TTLCache(Generic[T]):
    """A bounded ``key -> value`` cache with a fixed time-to-live.

    Not thread-local: one instance is meant to be a module-level singleton,
    shared by every request this worker process handles concurrently.
    """

    def __init__(self, ttl_seconds: float, max_entries: int = 256) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        #: ``key -> (stored_at, value)``. Insertion order is the eviction
        #: order, exactly as in ``geocoding_service``.
        self._store: dict[Hashable, tuple[float, T]] = {}
        self._store_lock = threading.Lock()
        #: One lock per key that has ever missed, so concurrent loads of
        #: different keys never wait on each other. Cleaned up alongside its
        #: key wherever the key leaves ``_store``, so this stays roughly the
        #: same size as the store rather than growing across the process
        #: lifetime.
        self._key_locks: dict[Hashable, threading.Lock] = {}

    def _key_lock(self, key: Hashable) -> threading.Lock:
        with self._store_lock:
            lock = self._key_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[key] = lock
            return lock

    def _read(self, key: Hashable) -> object:
        """Return the live value for ``key``, or ``_MISSING``.

        Must be called with ``_store_lock`` held. Drops the entry in place
        when it has aged past the TTL, so an expired key is indistinguishable
        from one never cached.
        """
        entry = self._store.get(key)
        if entry is None:
            return _MISSING
        stored_at, value = entry
        if time.monotonic() - stored_at > self._ttl:
            self._evict_locked(key)
            return _MISSING
        return value

    def _evict_locked(self, key: Hashable) -> None:
        """Drop one key from both maps. Must be called with ``_store_lock`` held."""
        self._store.pop(key, None)
        self._key_locks.pop(key, None)

    def get_or_load(self, key: Hashable, loader: Callable[[], T]) -> T:
        """Return the cached value for ``key``, computing it at most once.

        Two requests that miss at the same moment do not both call
        ``loader``: the second one blocks on the first's per-key lock and
        then finds the value it just stored, rather than repeating the read.
        """
        with self._store_lock:
            cached = self._read(key)
        if cached is not _MISSING:
            return cached  # type: ignore[return-value]

        with self._key_lock(key):
            # Re-check: whoever held the lock before us may have just
            # populated it.
            with self._store_lock:
                cached = self._read(key)
            if cached is not _MISSING:
                return cached  # type: ignore[return-value]

            value = loader()

            with self._store_lock:
                self._store[key] = (time.monotonic(), value)
                # Oldest-inserted first -- the same policy as the house
                # pattern, and all the eviction policy a reference cache of
                # this size needs.
                while len(self._store) > self._max_entries:
                    self._evict_locked(next(iter(self._store)))
            return value

    def invalidate(self, key: Hashable) -> None:
        """Drop one key. A no-op if it was not cached."""
        with self._store_lock:
            self._evict_locked(key)

    def invalidate_where(self, predicate: Callable[[Hashable], bool]) -> None:
        """Drop every key ``predicate`` accepts.

        For a cache whose key is a tuple -- the departments list, keyed by
        ``(community_id, search, status, page, page_size)`` -- a write does
        not know every filter combination a reader has cached, only the
        community it happened in. ``invalidate_where(lambda k: k[0] ==
        community_id)`` clears all of them at once.
        """
        with self._store_lock:
            stale = [key for key in self._store if predicate(key)]
            for key in stale:
                self._evict_locked(key)

    def clear(self) -> None:
        """Empty the cache. For tests: production code invalidates by key."""
        with self._store_lock:
            self._store.clear()
            self._key_locks.clear()
