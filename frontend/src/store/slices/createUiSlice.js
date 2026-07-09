// Transient UI state (the global search box). Not persisted / not cross-tab
// synced — a search term is per-tab, per-moment.
export const createUiSlice = (set) => ({
  searchQuery: '',
  setSearchQuery: (searchQuery) => set({ searchQuery }),
});
