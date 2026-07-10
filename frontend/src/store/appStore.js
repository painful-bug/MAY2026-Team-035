import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

import { createUiSlice } from './slices/createUiSlice';
import { createToastsSlice } from './slices/createToastsSlice';
import { createActivitiesSlice } from './slices/createActivitiesSlice';
import { createUsersSlice } from './slices/createUsersSlice';
import { createInvitationsSlice } from './slices/createInvitationsSlice';
import { createPendingRequestsSlice } from './slices/createPendingRequestsSlice';
import { createComplaintsSlice } from './slices/createComplaintsSlice';
import { createNoticesSlice } from './slices/createNoticesSlice';
import { createVisitorsSlice } from './slices/createVisitorsSlice';
import { createAmenitiesSlice } from './slices/createAmenitiesSlice';
import { createPaymentsSlice } from './slices/createPaymentsSlice';
import { createDepartmentsSlice } from './slices/createDepartmentsSlice';

// The whole domain layer. persist(...) writes it to localStorage on every
// change; a storage-event listener (store/sync.js) re-reads it in other tabs.
// That persistence + rehydrate is what fixes the cross-tab bug — a complaint
// raised in the resident tab lands in localStorage and the admin tab rehydrates.
export const useAppStore = create(
  persist(
    (set, get, api) => ({
      ...createUiSlice(set, get, api),
      ...createToastsSlice(set, get, api),
      ...createActivitiesSlice(set, get, api),
      ...createUsersSlice(set, get, api),
      ...createInvitationsSlice(set, get, api),
      ...createPendingRequestsSlice(set, get, api),
      ...createComplaintsSlice(set, get, api),
      ...createNoticesSlice(set, get, api),
      ...createVisitorsSlice(set, get, api),
      ...createAmenitiesSlice(set, get, api),
      ...createPaymentsSlice(set, get, api),
      ...createDepartmentsSlice(set, get, api),
    }),
    {
      name: 'homebandhu-app',
      storage: createJSONStorage(() => localStorage),
      // Allowlist the persisted collections. Omits functions (not serialisable
      // anyway) and transient UI (toasts, searchQuery) so those stay per-tab.
      partialize: (s) => ({
        users: s.users,
        invitations: s.invitations,
        pendingRequests: s.pendingRequests,
        complaints: s.complaints,
        notices: s.notices,
        visitors: s.visitors,
        bookings: s.bookings,
        payments: s.payments,
        amenities: s.amenities,
        activities: s.activities,
        departments: s.departments,
      }),
    }
  )
);
