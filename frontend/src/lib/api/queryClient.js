import { QueryClient, keepPreviousData } from '@tanstack/react-query';

// Doctrine (docs/ARCHITECTURE.md): the client React Query cache is the
// PRIMARY cache. Authenticated HTTP stays no-store end to end — nothing here
// asks the server to cache a response — and SSE frames (wired by a later
// agent) are hints that trigger *invalidation*, never a direct cache write.
// Everything below only controls how long a client-side read is trusted
// before the client asks the server again, and how long an unused entry
// survives in memory afterwards.
//
//   staleTime — how long a read is served from cache without a network call.
//   gcTime    — how long an entry survives in memory after its last observer
//               unmounts, before it is dropped and has to be refetched cold.
//
// Global fallback below covers the many call sites that specify neither
// (a modal's one-off detail fetch, a rarely-touched settings screen): it
// keeps the previous global default (30s staleTime) and adds an explicit
// gcTime everywhere, rather than leaving Query's own defaults (staleTime 0,
// gcTime 5min) in place, which would refetch on literally every mount.
const DEFAULT_STALE_TIME_MS = 30_000;
const DEFAULT_GC_TIME_MS = 5 * 60_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: DEFAULT_STALE_TIME_MS,
      gcTime: DEFAULT_GC_TIME_MS,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: { retry: 0 },
  },
});

/**
 * Per-domain cache policy. Spread the matching entry into a `useQuery` call
 * alongside its `queryKey`/`queryFn`, e.g.:
 *
 *   useQuery({
 *     queryKey: ['skills'],
 *     queryFn: workerApi.skills,
 *     ...QUERY_POLICIES.reference,
 *   });
 *
 * Deliberately four buckets, not a rule engine — a call site either matches
 * one of these or falls back to the global default above. Keep it that way;
 * a new bucket should earn its place the same way these did (a distinct,
 * recognizable class of data with a distinct acceptable staleness), not be
 * added per-screen.
 */
export const QUERY_POLICIES = {
  // Rarely-changing option lists: ['skills'], ['complaint-categories'],
  // ['department-options'], geo/community-search lookups. Whoever edits one
  // of these (an admin adding a skill, a category) sees the change on their
  // own screen regardless of staleTime, because their mutation invalidates
  // it directly — so everyone *else* can trust a half-hour-old copy.
  reference: { staleTime: 30 * 60_000, gcTime: 60 * 60_000 },

  // Dashboard/snapshot reads (worker/resident/admin home, security
  // overview, supervisor triage). The number on screen is a glance, not a
  // ledger — it stops mattering the moment it's more than about a minute
  // stale, so this trades a little staleness for far fewer refetches than
  // the previous global 30s default gave every one of these.
  snapshot: { staleTime: 45_000, gcTime: 5 * 60_000 },

  // Paginated/admin list screens (complaints, work orders, notices, people,
  // conversations, hiring rosters, security registers, ...): short enough
  // that a row created moments ago shows up on the next look, long enough
  // that switching tabs and back — or a filter round-trip — doesn't refetch
  // every time.
  list: { staleTime: 60_000, gcTime: 5 * 60_000 },

  // Single-record detail reads (a modal, a detail page). No staleTime
  // override — falls back to the client default above — but gcTime is
  // still explicit rather than left to Query's own default.
  detail: { gcTime: 5 * 60_000 },
};

// Spread onto a paginated/filtered list query alongside its policy, e.g.
//   useQuery({ queryKey: [...], queryFn, ...QUERY_POLICIES.list, ...PAGINATED })
// Keeps the previous page/filter's rows on screen (and `isPlaceholderData`
// true) while the next page loads, instead of collapsing the list to a
// loading state on every page or filter change.
export const PAGINATED = { placeholderData: keepPreviousData };
