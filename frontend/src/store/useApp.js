import { useAppStore } from './appStore';
import { useAuthStore } from './authStore';

// Selector-based facade over the two stores.
//
// Every consumer passes a one-key selector — `useApp((s) => s.showToast)` —
// and re-renders only when that one value changes. The hook subscribes to
// both stores with the same selector (zustand re-renders only when the
// selector's OUTPUT changes, so the wrong-store subscription yields a stable
// `undefined` and never re-renders), then answers from whichever store owns
// the key. Auth wins a collision, exactly as the old `{ ...app, ...auth }`
// spread did.
//
// Calling it with no selector keeps the old whole-both-stores subscription
// for any straggler call site, and re-renders on every state change — do not
// add new call sites that way.
const identity = (state) => state;

export function useApp(selector) {
  const fromApp = useAppStore(selector ?? identity);
  const fromAuth = useAuthStore(selector ?? identity);
  if (!selector) return { ...fromApp, ...fromAuth };
  return selector(useAuthStore.getState()) === undefined ? fromApp : fromAuth;
}
