import { useEffect, useState } from 'react';

/**
 * A value that settles after the caller stops changing it.
 *
 * 250 ms by default: the interval that makes a suggestion list feel like it is
 * keeping up while still collapsing a typed word into roughly one request. The
 * timer is cleared on every change, so a fast typist issues one call rather
 * than one per letter.
 *
 * In its own file because a hook exported beside a component breaks Vite's fast
 * refresh for that component — the whole module reloads instead of the element.
 */
export function useDebounced(value, delay = 250) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return settled;
}
