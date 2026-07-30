# Changelog

All notable user-visible and architectural changes are recorded here. This
repository follows a single unreleased change set while the Google-auth and
database-dashboard migration is being integrated.

## Unreleased

### Added

- Provider-neutral Supabase authentication: Google OAuth remains primary and
  verified email/password is an opt-in secondary method, configured entirely
  through `AUTH_PRIMARY_METHOD` and `AUTH_ENABLED_METHODS`.
- Explicit email-confirmation and password-recovery pages, pre-auth CSRF
  protection, short-lived recovery cookies, best-effort server-side logout
  revocation, and 30-day sliding refresh cookies.
- Reversible `blacklisted_residents` records plus an atomic administrator
  blacklist action. Blacklisted communities are omitted from that identity's
  onboarding search without exposing the blacklist reason.
- Forward-only Supabase compatibility migrations for legacy hosted projects:
  blacklist-aware directory search, canonical community statuses,
  access-request profile ownership, and resident approval/rejection RPCs.

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

- The authentication screen is now unified and the landing page has one Get
  Started action. Browser code still never calls Supabase directly or stores
  provider/session tokens.
- Community membership is the source of tenant identity and permissions for
  every authenticated backend endpoint.
- Dashboard collections in Zustand are now an ephemeral render cache. They are
  hydrated from `/api/v1/dashboard/snapshot`, cleared on logout, and are never
  persisted in `localStorage`.
- Dashboard pages consume normalized database projections for members,
  complaints, visitors, amenities, bookings, invoices/payments, notices,
  departments, and activity.
- Community directory search now normalizes legacy title-cased statuses to the
  canonical `active` value and prevents future non-canonical status writes.
- Resident approval is compatible with both legacy and fresh partial-unique
  membership indexes, while preserving legacy invoice-oriented RPC overloads.
- The Join Community phone control separates country code from the local phone
  number, defaults to `+91`, and submits the resulting E.164 value.

### Removed

- Retired browser-side Supabase authentication, OTP/password routes, local
  invitation-token implementation, fixture-backed dashboard collections, and
  unused amenity browser-persistence adapters.
- Tracked Python bytecode and unused default Vite logo assets.

See [frontend changes](docs/FRONTEND_CHANGES.md) and
[backend changes](docs/BACKEND_CHANGES.md) for the implementation detail and
current data-flow boundaries.
