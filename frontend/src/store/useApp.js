import { useAppStore } from './appStore';
import { useAuthStore } from './authStore';

// Backwards-compatible facade. Existing pages call useApp() and destructure the
// same keys the old React context exposed, so nothing downstream had to change.
// Subscribes to both whole stores — same re-render granularity as the old single
// context. If a hot page ever needs it, swap to a scoped selector, e.g.
// useAppStore(s => s.complaints), right in that component.
export function useApp() {
  const app = useAppStore();
  const auth = useAuthStore();
  return { ...app, ...auth };
}
