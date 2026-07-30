import { genId } from '../../lib/ids';

// Recent-activity timeline shown on dashboard home pages. Every mutating action
// pushes one entry here (via get().addActivity) — same convention as the toasts.
export const createActivitiesSlice = (set) => ({
  activities: [],
  addActivity: (text, type = 'general') =>
    set((s) => ({
      activities: [{ id: genId('act'), text, time: 'Just Now', type }, ...s.activities],
    })),
});
