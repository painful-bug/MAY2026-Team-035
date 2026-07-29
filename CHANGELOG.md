# Changelog

All notable user-visible and architectural changes are recorded here. This
repository follows a single unreleased change set while the Google-auth and
database-dashboard migration is being integrated.

## Unreleased

### Added

- Backend-owned Google OAuth using Supabase PKCE, signed HTTP-only session and
  refresh cookies, and CSRF protection for state-changing requests.
- Registration onboarding for creating a community or requesting to join an
  existing one, plus administrator-created resident invitations.
- A tenant-scoped dashboard snapshot endpoint and same-origin Server-Sent
  Events (SSE) stream. Browser dashboard state is refreshed from the database
  whenever a community record changes.
- Database migrations for the clean baseline, legacy founder-onboarding
  compatibility, and the dashboard realtime outbox.
- API-backed amenity creation, editing, activation, and removal for authorized
  administrators and managers.

### Changed

- Authentication is Google-only. The browser no longer calls Supabase directly,
  stores provider tokens, or implements password, OTP, or magic-link auth.
- Community membership is the source of tenant identity and permissions for
  every authenticated backend endpoint.
- Dashboard collections in Zustand are now an ephemeral render cache. They are
  hydrated from `/api/v1/dashboard/snapshot`, cleared on logout, and are never
  persisted in `localStorage`.
- Dashboard pages consume normalized database projections for members,
  complaints, visitors, amenities, bookings, invoices/payments, notices,
  departments, and activity.

### Removed

- Retired browser-side Supabase authentication, OTP/password routes, local
  invitation-token implementation, fixture-backed dashboard collections, and
  unused amenity browser-persistence adapters.
- Tracked Python bytecode and unused default Vite logo assets.

See [frontend changes](docs/FRONTEND_CHANGES.md) and
[backend changes](docs/BACKEND_CHANGES.md) for the implementation detail and
current data-flow boundaries.
