"""Unit tests for the shared TTL cache utility (Phase B2 -- ``app.core.ttl_cache``).

These exercise the utility in isolation, with no Supabase client or FastAPI
involved: hit/miss, expiry, bounded eviction, single-flight coalescing under
real concurrent threads, and both invalidation shapes (`invalidate` by exact
key, `invalidate_where` by predicate).
"""

from __future__ import annotations

import threading
import time

import pytest

from app.core import ttl_cache as ttl_cache_module
from app.core.ttl_cache import TTLCache


def _fail(*_args, **_kwargs):
    raise AssertionError("loader should not have been called -- expected a cache hit")


def test_a_hit_never_calls_the_loader():
    cache = TTLCache(ttl_seconds=60)
    calls = []

    def loader():
        calls.append(1)
        return "value"

    assert cache.get_or_load("k", loader) == "value"
    assert cache.get_or_load("k", loader) == "value"
    assert cache.get_or_load("k", loader) == "value"
    assert len(calls) == 1


def test_distinct_keys_each_miss_independently():
    cache = TTLCache(ttl_seconds=60)
    calls = []

    def loader():
        calls.append(1)
        return len(calls)

    assert cache.get_or_load("a", loader) == 1
    assert cache.get_or_load("b", loader) == 2
    # Both are now cached in their own right.
    assert cache.get_or_load("a", loader) == 1
    assert cache.get_or_load("b", loader) == 2
    assert len(calls) == 2


def test_expiry_reloads_once_the_ttl_has_passed(monkeypatch: pytest.MonkeyPatch):
    cache = TTLCache(ttl_seconds=10)
    calls = []
    now = [1_000.0]
    monkeypatch.setattr(ttl_cache_module.time, "monotonic", lambda: now[0])

    def loader():
        calls.append(1)
        return len(calls)

    assert cache.get_or_load("k", loader) == 1
    now[0] += 5  # still inside the 10-second window
    assert cache.get_or_load("k", loader) == 1
    assert len(calls) == 1

    now[0] += 6  # 11 seconds since the store, past the TTL
    assert cache.get_or_load("k", loader) == 2
    assert len(calls) == 2


def test_bounded_eviction_drops_the_oldest_entry_first():
    cache = TTLCache(ttl_seconds=60, max_entries=2)
    cache.get_or_load("a", lambda: "A")
    cache.get_or_load("b", lambda: "B")
    # A third distinct key pushes the store past its cap; "a" was inserted
    # first, so it is the one evicted -- the same oldest-inserted policy
    # ``geocoding_service`` uses.
    cache.get_or_load("c", lambda: "C")

    reload_calls = []

    def reload_a():
        reload_calls.append(1)
        return "A-reloaded"

    assert cache.get_or_load("a", reload_a) == "A-reloaded"
    assert len(reload_calls) == 1  # "a" really was evicted, not just untouched

    # "c" was the most recent insert before "a" came back and is still within
    # the cap, so it is still served from cache. ("b" is not asserted here:
    # reinserting "a" pushed the store to three entries again and evicted
    # whichever was then oldest -- "b" -- which is the same policy, not a
    # second bug.)
    assert cache.get_or_load("c", _fail) == "C"


def test_single_flight_runs_the_loader_once_for_concurrent_callers():
    """Two threads missing on the same key at once must not both load.

    The loader blocks until both callers have arrived, which would deadlock
    (and fail the test on the join timeout) if the second caller's
    ``get_or_load`` returned early with its own loader invocation rather than
    waiting on the first one's.
    """
    cache = TTLCache(ttl_seconds=60)
    call_count = []
    first_call_started = threading.Event()
    release_loader = threading.Event()

    def loader():
        call_count.append(1)
        first_call_started.set()
        assert release_loader.wait(timeout=5), "second thread never arrived"
        return "value"

    results: list[str] = []

    def run():
        results.append(cache.get_or_load("k", loader))

    t1 = threading.Thread(target=run)
    t2 = threading.Thread(target=run)

    t1.start()
    assert first_call_started.wait(timeout=5)
    t2.start()
    # Give the second thread a moment to reach the per-key lock and block on
    # it, rather than racing to call the loader itself.
    time.sleep(0.1)
    release_loader.set()

    t1.join(timeout=5)
    t2.join(timeout=5)

    assert results == ["value", "value"]
    assert len(call_count) == 1


def test_invalidate_forces_the_next_read_to_reload():
    cache = TTLCache(ttl_seconds=60)
    calls = []

    def loader():
        calls.append(1)
        return len(calls)

    assert cache.get_or_load("k", loader) == 1
    cache.invalidate("k")
    assert cache.get_or_load("k", loader) == 2
    # Invalidating a key nobody cached is a no-op, not an error.
    cache.invalidate("never-cached")


def test_invalidate_where_only_drops_matching_keys():
    cache = TTLCache(ttl_seconds=60)
    cache.get_or_load(("community-1", "page-1"), lambda: "c1p1")
    cache.get_or_load(("community-1", "page-2"), lambda: "c1p2")
    cache.get_or_load(("community-2", "page-1"), lambda: "c2p1")

    cache.invalidate_where(lambda key: key[0] == "community-1")

    reload_calls = []

    def reload():
        reload_calls.append(1)
        return "reloaded"

    assert cache.get_or_load(("community-1", "page-1"), reload) == "reloaded"
    assert cache.get_or_load(("community-1", "page-2"), reload) == "reloaded"
    assert len(reload_calls) == 2
    # community-2's entry was never touched.
    assert cache.get_or_load(("community-2", "page-1"), _fail) == "c2p1"


def test_clear_empties_the_whole_cache():
    cache = TTLCache(ttl_seconds=60)
    cache.get_or_load("a", lambda: "A")
    cache.get_or_load("b", lambda: "B")
    cache.clear()

    calls = []
    assert cache.get_or_load("a", lambda: calls.append(1) or "A-again") == "A-again"
    assert len(calls) == 1
