import { useAppStore } from './appStore';

// Realtime cross-tab hydration. The `storage` event fires in OTHER tabs when one
// tab writes localStorage; we re-read the persisted app state so this tab's
// components re-render with the new data. This is what makes a resident's
// complaint show up in the admin tab with no manual reload (PRD "Dynamic
// Hydration"). Auth (sessionStorage) is intentionally not synced — each tab
// keeps its own session.
export function initCrossTabSync() {
  window.addEventListener('storage', (e) => {
    if (e.key === 'homebandhu-app' && e.newValue !== e.oldValue) {
      useAppStore.persist.rehydrate();
    }
  });
}
