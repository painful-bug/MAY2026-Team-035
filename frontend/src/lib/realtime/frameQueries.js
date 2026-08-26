// Frame → query keys. The pure half of the live-update wiring, and the only
// half worth a unit test: the hook around it is `subscribeToStream` plus a
// `for` loop, while *which read a frame makes stale* is the thing that can be
// got wrong, and its failure is silent — a screen that quietly stops updating.
//
// Generalised out of `features/resident/residentEvents.js`, whose per-portal
// behaviour is now one of the maps below (it kept its own file, because it also
// owns `residentKeys`). The split it established survives: a pure mapper here,
// a hook in `useLiveUpdates.js`, and nothing in between that renders a payload.

/**
 * The prefix every query key starts with, so invalidating it invalidates the
 * whole cache. React Query matches keys by prefix, and `[]` is a prefix of
 * everything — this is `queryClient.invalidateQueries()` expressed as a key, so
 * that "re-read everything" stays inside the pure mapper instead of becoming a
 * special case the hook has to branch on.
 */
export const ALL_QUERIES = Object.freeze([]);

/**
 * @typedef {object} PortalEventMap
 * @property {Array<Array<string>>} [always]
 *   Invalidated by every frame this portal does not treat as a resync. The
 *   portal's cheapest "something happened here" read — a snapshot, a feed —
 *   which is also what covers an unnamed frame carrying no topic at all.
 * @property {Array<Array<string>>} [resync]
 *   The answer to `stream.resync`: "you have a gap, everything you show may be
 *   stale." Defaults to `always`; use `[ALL_QUERIES]` for a portal whose reads
 *   are too scattered to enumerate honestly.
 * @property {Record<string, Array<Array<string>>>} [topics]
 *   Extra keys per topic. A topic absent from here contributes nothing beyond
 *   `always`, which is deliberate: a topic a later backend adds shows up as a
 *   cheap snapshot re-read rather than as nothing.
 * @property {Record<string, Array<Array<string>>>} [kinds]
 *   Extra keys per *notification kind family* — the part of `kind` before the
 *   first dot, e.g. `complaint` for `complaint.resolved`. Only consulted for
 *   `notification.created` (and an unnamed frame), because that is the only
 *   topic carrying a `kind`.
 */

const sameKey = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function dedupe(keys) {
  const out = [];
  for (const key of keys) {
    if (!out.some((seen) => sameKey(seen, key))) out.push(key);
  }
  return out;
}

/** The one topic that carries a `kind`, plus the unnamed frame that may. */
const KIND_BEARING = new Set([undefined, null, '', 'message', 'notification.created']);

/**
 * Which queries one frame makes stale, under one portal's map. Pure.
 *
 * @param {{topic?: string, kind?: string, resync?: boolean}} frame
 * @param {PortalEventMap} map
 * @returns {Array<Array<string>>} query keys, each an invalidation prefix
 */
export function queriesForFrame(frame = {}, map = {}) {
  const { topic, kind, resync } = frame;
  const always = map.always || [];

  // "You have a gap, re-read everything." The only frame with no domain event
  // behind it, and the one every client must handle — the server prepends it
  // when a reconnecting client's `Last-Event-ID` predates the prune horizon.
  if (resync === true || topic === 'stream.resync') {
    return dedupe(map.resync || always);
  }

  const keys = [...always];

  const topics = map.topics || {};
  if (topic && Object.prototype.hasOwnProperty.call(topics, topic)) {
    keys.push(...topics[topic]);
  }

  if (KIND_BEARING.has(topic)) {
    const family = String(kind || '').split('.')[0];
    const kinds = map.kinds || {};
    if (family && Object.prototype.hasOwnProperty.call(kinds, family)) {
      keys.push(...kinds[family]);
    }
  }

  return dedupe(keys);
}

/** How often a degraded tab re-reads when the stream is not carrying frames. */
export const SSE_FALLBACK_INTERVAL_MS = 5 * 60_000;

/**
 * The uniform fallback rule (C3), as a pure function so it can be tested
 * without a connection: SSE invalidation replaces the fast poll outright, and a
 * slow poll survives ONLY while the stream is unavailable or in error.
 *
 * Returns React Query's `refetchInterval` value — `false` disables polling.
 *
 * @param {boolean} streamLive
 * @param {number} [degradedMs]
 * @returns {number|false}
 */
export function sseFallbackInterval(streamLive, degradedMs = SSE_FALLBACK_INTERVAL_MS) {
  return streamLive ? false : degradedMs;
}
