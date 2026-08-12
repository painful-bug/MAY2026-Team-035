// The one definition of "this provider profile is complete enough to use the
// worker portal". WorkerLayout gates the whole chrome on it, and ChatDock
// hides the floating bubble on it while on the worker surface. Import it;
// never copy it.
//
// It lives in its own module rather than inside workerApi.js on purpose:
// tests mock the workerApi module wholesale (vi.mock), and a predicate that
// travelled with it would be clobbered by every one of those mocks.
//
// Completeness, not existence, is the point: a provider row can exist but be
// unusable — registration submitted without coordinates, or with no active
// skill — and those users belong on the registration screen, prefilled.
export function isProviderProfileComplete(provider) {
  return provider?.latitude != null
    && provider?.longitude != null
    && (provider?.skillIds?.length ?? 0) > 0;
}
