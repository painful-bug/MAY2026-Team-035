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
      // Trailing-7-day creation counts for the dashboard trend chips —
      // `{ residents, complaints, visitorRequests, bookings }`, all integers
      // (fixed contract with the snapshot endpoint). `null` until a snapshot
      // that carries it arrives, and the chips render nothing for `null`, so
      // the UI is truthful against both the current backend and the one adding
      // the field.
      weeklyNew: null,
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
        weeklyNew: snapshot.weeklyNew ?? null,
      }),
      clearDashboard: () => set({
        users: [], complaints: [], visitors: [], amenities: [], bookings: [],
        payments: [], notices: [], departments: [], activities: [], pendingRequests: [],
        weeklyNew: null,
      }),
    }));
