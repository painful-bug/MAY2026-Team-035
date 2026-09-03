import { useEffect, useSyncExternalStore } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { isStreamLive, subscribeToStream, subscribeToStreamState } from './eventStream.js';
import { queriesForFrame, SSE_FALLBACK_INTERVAL_MS, sseFallbackInterval } from './frameQueries.js';

/**
 * Keep a portal's screens current while it is open.
 *
 * Mounted once per portal, in the layout, so that it covers every page under
 * it and closes with the portal rather than with a navigation. (`ChatDock` and
 * `NotificationBell` mount it themselves with their own small maps, because
 * they render in portals — admin — that have no layout-level mount.)
 *
 * The stream failing is not an error state on screen: the queries below it have
 * their own, and a browser with no backend at all should show the page's empty
 * state rather than a banner about a transport.
 *
 * @param {import('./frameQueries.js').PortalEventMap} map
 *   Must be a stable reference — a module-level constant, not an object literal
 *   built in the component body, which would resubscribe on every render.
 * @param {{enabled?: boolean}} [options]
 */
export function useLiveUpdates(map, { enabled = true } = {}) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || !map) return undefined;
    return subscribeToStream((frame) => {
      for (const queryKey of queriesForFrame(frame, map)) {
        queryClient.invalidateQueries({ queryKey });
      }
    });
  }, [queryClient, map, enabled]);
}

/** Whether the shared stream is currently carrying frames. */
export function useStreamLive() {
  return useSyncExternalStore(subscribeToStreamState, isStreamLive, () => false);
}

/**
 * The `refetchInterval` a poll should use, under the one fallback rule (C3).
 *
 * `false` while the stream is live — the frames are the refresh. The slow
 * interval otherwise, which is the whole of what a browser with no
 * `EventSource`, or a tab whose stream has dropped, still gets.
 *
 * @param {number} [degradedMs]
 * @returns {number|false}
 */
export function useSseFallbackInterval(degradedMs = SSE_FALLBACK_INTERVAL_MS) {
  return sseFallbackInterval(useStreamLive(), degradedMs);
}
