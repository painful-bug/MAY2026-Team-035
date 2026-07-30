import { create } from 'zustand';

import { createUiSlice } from './slices/createUiSlice';
import { createToastsSlice } from './slices/createToastsSlice';
import { createActivitiesSlice } from './slices/createActivitiesSlice';
import { createUsersSlice } from './slices/createUsersSlice';
import { createPendingRequestsSlice } from './slices/createPendingRequestsSlice';
import { createComplaintsSlice } from './slices/createComplaintsSlice';
import { createNoticesSlice } from './slices/createNoticesSlice';
import { createVisitorsSlice } from './slices/createVisitorsSlice';
import { createAmenitiesSlice } from './slices/createAmenitiesSlice';
import { createPaymentsSlice } from './slices/createPaymentsSlice';
import { createDepartmentsSlice } from './slices/createDepartmentsSlice';

// Browser state is a render cache only.  Tenant records are hydrated from the
// backend snapshot and refreshed by the authenticated SSE stream; localStorage
// is deliberately never a source of domain truth.
export const useAppStore = create((set, get, api) => ({
      ...createUiSlice(set, get, api),
      ...createToastsSlice(set, get, api),
      ...createActivitiesSlice(set, get, api),
      ...createUsersSlice(set, get, api),
      ...createPendingRequestsSlice(set, get, api),
      ...createComplaintsSlice(set, get, api),
      ...createNoticesSlice(set, get, api),
      ...createVisitorsSlice(set, get, api),
      ...createAmenitiesSlice(set, get, api),
      ...createPaymentsSlice(set, get, api),
      ...createDepartmentsSlice(set, get, api),
      hydrateDashboard: (snapshot) => set({
        users: snapshot.users ?? [],
        complaints: snapshot.complaints ?? [],
        visitors: snapshot.visitors ?? [],
        amenities: snapshot.amenities ?? [],
        bookings: snapshot.bookings ?? [],
        payments: snapshot.payments ?? [],
        notices: snapshot.notices ?? [],
        departments: snapshot.departments ?? [],
        activities: snapshot.activities ?? [],
        pendingRequests: snapshot.pendingRequests ?? [],
      }),
      clearDashboard: () => set({
        users: [], complaints: [], visitors: [], amenities: [], bookings: [],
        payments: [], notices: [], departments: [], activities: [], pendingRequests: [],
      }),
    }));
