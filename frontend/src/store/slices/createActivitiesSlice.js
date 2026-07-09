import { genId } from '../../lib/ids';

const seedActivities = [
  { id: 'act1', text: 'You pre-approved visitor Rahul Verma', time: '10 mins ago', type: 'visitor' },
  { id: 'act2', text: 'Water tank cleaning notice posted by Admin', time: '2 hours ago', type: 'notice' },
  { id: 'act3', text: 'You raised complaint "Leaking tap in kitchen"', time: '2 hours ago', type: 'complaint' },
  { id: 'act4', text: 'Paid maintenance bill for June 2026', time: '2 days ago', type: 'payment' },
];

// Recent-activity timeline shown on dashboard home pages. Every mutating action
// pushes one entry here (via get().addActivity) — same convention as the toasts.
export const createActivitiesSlice = (set) => ({
  activities: seedActivities,
  addActivity: (text, type = 'general') =>
    set((s) => ({
      activities: [{ id: genId('act'), text, time: 'Just Now', type }, ...s.activities],
    })),
});
