# Frontend changes

## Scope

The frontend is now a same-origin React client for the FastAPI API. It does not
import a Supabase SDK, retain provider credentials, or treat browser storage as
tenant data. The selected authentication mechanism and all authorization
decisions are resolved by the backend.

## Authentication and registration

`src/lib/api/client.js` is the one HTTP boundary. It sends cookies with every
request, attaches the readable CSRF cookie to unsafe methods, and performs one
refresh attempt after an unauthorized response. `src/lib/auth/authService.js`
and `src/store/authStore.js` use that boundary to:

- fetch the server session;
- start Google sign-in at `/api/v1/auth/google/start`;
- complete the callback by re-reading the server session;
- redeem a previously prepared invitation; and
- clear the client session after backend logout.

Routes and pages for passwords, phone OTP, resident-local login, and direct
Supabase authentication were removed. `AuthEntryPage`, `RegistrationPage`, and
the registration feature provide the supported entry points: Google sign-in,
create-community onboarding, community search, join requests, and invitation
redemption.

## Dashboard data flow

`src/components/dashboard/DashboardDataBootstrap.jsx` is mounted once in
`App.jsx`. After the authenticated session is ready it performs this sequence:

1. It calls `GET /api/v1/dashboard/snapshot`.
2. It writes the returned projection into `useAppStore` with
   `hydrateDashboard`.
3. It opens an `EventSource` to `GET /api/v1/dashboard/events`.
4. On `dashboard.refresh`, it debounces another snapshot request and dispatches
   `homebandhu:dashboard-refresh` so feature views can reload derived data.
5. On logout, it calls `clearDashboard`; no tenant data survives in local
   storage.

`src/lib/dashboard/dashboardApi.js` isolates the snapshot and SSE protocol,
which keeps future transport changes out of dashboard views. `src/store/appStore.js`
is deliberately a render cache: its domain collections begin empty and only
the snapshot hydrator supplies records.

The snapshot contains normalized UI records for users, complaints, visitors,
amenities, bookings, invoices/payments, notices, departments, and activity.
Resident visibility is additionally constrained by the backend so a resident
only receives their own complaints, visitor requests, and invoices.

## Amenity management

`src/features/amenities/services/amenitiesService.js` reads current amenities
from the snapshot and sends administrator/manager mutations to the dashboard
API. The service maps the existing form model to the API DTO, so pages and form
components did not need duplicate request logic. Each successful mutation is
subsequently reflected by the SSE-triggered snapshot refresh.

Booking reads use the same snapshot protocol. Their local cache is only a
short-lived derived view while a page is open; it is not persisted. Financial
ledger UI keeps no seeded transactions or browser persistence. Booking and
ledger mutation endpoints remain a follow-up integration boundary and must not
be represented as durable client-only records.

## Retired client code

The following categories were removed after an import-graph audit:

- fixture data for dashboard users, complaints, visitors, payments, amenities,
  bookings, notices, departments, administrators, and requests;
- three unused amenity `localStorage` persistence adapters;
- the unused local invitation/token/redeem slice and its self-check;
- unused default Vite image assets; and
- password/OTP/direct-Supabase authentication components and routes.

Static onboarding metadata, admin designation options, and resident FAQs remain
in `src/data` because their current components import them as application
configuration or help content rather than tenant records.

## Validation

- `npm run build` validates the production Vite bundle.
- `npm run lint` runs the configured frontend lint check.
- Runtime validation requires a signed-in member: use the browser Network panel
  to confirm a 200 snapshot request and a long-lived SSE request. A new
  community legitimately starts with empty database collections rather than
  fixture data.
