import { genId } from '../../lib/ids';

// Transient toast notifications. Excluded from persistence (see appStore
// partialize) so they don't survive reloads or leak across tabs.
export const createToastsSlice = (set) => ({
  toasts: [],
  showToast: (message, type = 'success') => {
    const id = genId('toast');
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
});
