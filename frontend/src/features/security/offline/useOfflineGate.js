import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { securityApi } from '../securityApi';
import {
  applyOutcomes,
  bundleUsable,
  dismissEntry,
  enqueueScan,
  loadBundle,
  loadQueue,
  pendingEntries,
  saveBundle,
  saveQueue,
  toReconcilePayload,
  verifyLocal,
} from './offlineGate';

/**
 * The gate screen's offline half: cached bundle, connectivity, queue, reconcile.
 *
 * `navigator.onLine` is used here and nowhere else in this project. It is a
 * weak signal — it reports a link, not reachability — so it decides only which
 * *path the scan takes first*, and a failed online verify falls back to the
 * local one anyway. The banner follows the same flag because a guard needs to
 * know the answers they are getting are provisional, and a slightly early
 * banner is a much smaller problem than a silently provisional admission.
 */
export function useOfflineGate() {
  const [online, setOnline] = useState(() => globalThis.navigator?.onLine !== false);
  const [queue, setQueue] = useState(() => loadQueue());
  const [cached, setCached] = useState(() => loadBundle());
  const [outcome, setOutcome] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState(null);
  const syncingRef = useRef(false);

  // Refresh the bundle while there is a network. Half-hourly rather than on
  // demand, because the moment it is needed is the moment it cannot be fetched.
  const bundle = useQuery({
    queryKey: ['security', 'offline-bundle'],
    queryFn: () => securityApi.offlineBundle(12),
    refetchInterval: 30 * 60 * 1000,
    enabled: online,
  });

  useEffect(() => {
    if (bundle.data) {
      saveBundle(bundle.data);
      setCached(loadBundle());
    }
  }, [bundle.data]);

  const persist = useCallback((next) => {
    setQueue(next);
    saveQueue(next);
    return next;
  }, []);

  const sync = useCallback(async () => {
    if (syncingRef.current) return;
    const pending = pendingEntries(loadQueue());
    if (pending.length === 0) return;

    syncingRef.current = true;
    setSyncing(true);
    setSyncError(null);
    try {
      const result = await securityApi.offlineReconcile(toReconcilePayload(pending));
      persist(applyOutcomes(loadQueue(), result.outcomes));
      setOutcome(result);
    } catch (error) {
      // The queue is untouched on failure, which is the whole point of it.
      setSyncError(error);
    } finally {
      syncingRef.current = false;
      setSyncing(false);
    }
  }, [persist]);

  useEffect(() => {
    const goOnline = () => {
      setOnline(true);
      void sync();
    };
    const goOffline = () => setOnline(false);
    globalThis.addEventListener?.('online', goOnline);
    globalThis.addEventListener?.('offline', goOffline);
    return () => {
      globalThis.removeEventListener?.('online', goOnline);
      globalThis.removeEventListener?.('offline', goOffline);
    };
  }, [sync]);

  // A queue that survived a reload is reconciled as soon as the screen mounts
  // with a network — the guard should not have to remember to press anything.
  useEffect(() => {
    if (online) void sync();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Verify while disconnected. Returns the provisional verdict and queues it.
   *
   * Every scan is queued, including `not_found`: a code the cached list does
   * not recognise is exactly the entry an admin most needs to see reconciled,
   * because it is either a stale cache or somebody at the barrier with a code
   * this gate never issued.
   */
  const verifyOffline = useCallback(
    async (credential) => {
      const usable = bundleUsable(cached);
      const verdict = usable
        ? await verifyLocal(credential, cached.bundle)
        : {
            verdict: 'not_found',
            detail:
              'The cached pass list has expired, so this device cannot check the code. Record the entry in the registers instead.',
          };
      if (usable) persist(enqueueScan(loadQueue(), { credential, verdict }));
      return verdict;
    },
    [cached, persist]
  );

  return {
    online,
    bundle: cached?.bundle || null,
    bundleUsable: bundleUsable(cached),
    bundleFetchedAt: cached?.fetchedAt || null,
    bundleQuery: bundle,
    queue,
    pending: pendingEntries(queue),
    rejected: queue.filter((entry) => entry.status === 'rejected'),
    verifyOffline,
    sync,
    syncing,
    syncError,
    outcome,
    clearOutcome: () => setOutcome(null),
    dismiss: (sourceClientId) => persist(dismissEntry(loadQueue(), sourceClientId)),
  };
}
