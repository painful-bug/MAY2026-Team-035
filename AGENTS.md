# AGENTS.md

This file provides guidance to AI coding agents (Codex, Claude Code, etc.) when working with code in this repository.

## Project overview

"HomeBandhu" — a residential society/apartment management app. React 19 + Vite + Tailwind CSS v4. There is **no backend**: all data lives in Zustand stores seeded from static arrays in `frontend/src/data/`. State is persisted to browser storage, so it survives reloads and syncs across tabs.

Two largely independent user journeys share the same codebase:
- **Resident/admin dashboards** — day-to-day app (visitors, complaints, amenities, payments, notices, resident/admin management). This is what most of `pages/`, `layouts/`, and `appStore.js` serve.
- **Admin association onboarding** — a multi-step wizard (`/login` → OTP → association details → map configuration → feature configuration → admin profile → OTP → success) that provisions a brand-new association and its first Admin. This is a separate state machine (`authStore.js` + `onboardingStore.js`) layered on top of the same login page. See "Admin onboarding wizard" below.

Monorepo (npm workspaces for the frontend): all SPA code is in `frontend/`. `backend/` now holds a **real backend** — a Python **FastAPI** service over **Supabase** (Postgres + Auth + Storage) — that is being built out; the frontend is not yet wired to it (it still runs entirely on the Zustand/localStorage mock layer). See "Backend" below.

`docs/DESIGN.md` is the authoritative visual-language reference (typography, color, radius, elevation tables) — consult it before adding new UI. `docs/CLAUDE.md` mirrors this file for Claude Code; keep both in sync if you change one. `docs/AGENTS.md` is an older, largely superseded planning document (predates the `features/` module, the onboarding wizard, and the Supabase backend — and its "future stack: Node/Express/Prisma" note is now wrong; the chosen stack is Python/FastAPI/Supabase) — prefer this file when the two disagree.

## Commands

Run from the repo root (scripts proxy to the `frontend` workspace via `-w frontend`):

```bash
npm install       # once, from root — installs the frontend workspace
npm run dev       # start Vite dev server
npm run build     # production build
npm run preview   # preview the production build locally
npm run lint      # oxlint (rules in frontend/.oxlintrc.json)
```

No test runner is configured. Pure logic has framework-free node self-checks:
`node frontend/src/lib/selfcheck.mjs` (invite tokens + redemption).

Package manager: root `package-lock.json` owns the workspace; a stale `frontend/bun.lock` also exists — prefer npm, don't mix.

## Architecture

**Three Zustand stores, no backend, persisted + cross-tab synced.** The data layer is `frontend/src/store/`, not a React context (there is no provider — Zustand is provider-less):

- **`appStore.js`** — every domain collection (`users`, `invitations`, `pendingRequests`, `complaints`, `notices`, `visitors`, `bookings`, `payments`, `amenities`, `activities`) plus their actions. Composed from `store/slices/create*Slice.js`, one slice per domain, each a `(set, get) => ({ <collection>, ...actions })` creator seeded from `src/data/*.js`. Persisted to **localStorage** via the `persist` middleware; `partialize` allowlists the collections and omits transient UI (`toasts`, `searchQuery`).
- **`authStore.js`** — `currentUser` plus a small **admin auth state machine** (see below). Persisted to **sessionStorage** so each browser tab keeps its own session (a resident tab and an admin tab stay independently logged in while sharing the same domain data).
- **`onboardingStore.js`** — draft state for the admin association-onboarding wizard (association name/type, blocks/villas + their map coordinates, enabled feature modules, admin profile, completion flags). Persisted to **sessionStorage** (`homebandhu-admin-onboarding`, versioned with a `migrate` function — bump `version` and extend `migrate` when the shape changes, don't just rename fields). Composed the same way as `appStore` from `store/slices/createOnboarding*Slice.js`.
- **`sync.js`** (`initCrossTabSync`, called once in `main.jsx`) — a `storage`-event listener that calls `useAppStore.persist.rehydrate()` so a change in one tab re-renders the others with no reload. This is the "realtime hydration" the PRD asks for and the fix for the reported cross-tab bug.
- **`useApp.js`** — a `useApp()` facade that merges `appStore` + `authStore` into the object shape the old React context exposed, so pages didn't have to change. For a hot component, subscribe with a scoped selector instead, e.g. `useAppStore(s => s.complaints)`.

Cross-slice actions reach siblings via `get()` (e.g. `acceptRequest` writes users + payments + pendingRequests in one `set`). Cross-store access is at call time via `getState()` (e.g. `login` reads `useAppStore.getState().users`; slices that need the logged-in user read `useAuthStore.getState().currentUser`). appStore and authStore import each other — this circular import is safe because nothing crosses stores during module evaluation, only inside action bodies.

When adding a stateful feature to the main app: add a seed array to `src/data/`, add a `create<Domain>Slice.js`, compose it in `appStore.js`, and (if it needs the same keys as before) it's already exposed through `useApp()`. Each mutating action should call `get().showToast(...)` and `get().addActivity(...)` like the rest.

**Auth has two paths, both simulated.**
- Legacy demo shortcut: `login(phone)` in `authStore.js` matches the phone against `users` (plus demo accounts in `data/authentication.js`: resident `9876543210` = u1, admin `9999988888` = u2) and logs in directly, no OTP check. Used by the resident login form and demo buttons.
- Admin phone+OTP flow: `startAdminAuthentication()` → `submitAdminOtp()` drive an explicit **`AUTH_FLOW_STATE`** machine (`idle → checking_registration → otp_required → otp_submitting → authenticated`, or `→ registration_required` if the phone isn't in `data/admins.js#registeredAdmins`). Route guards key off this state (see below); the OTP value itself is never checked — `services/adminAuthService.js` only checks phone registration, mirroring a future verify-OTP API contract.
"Logged in" for either path is just `currentUser` being non-null in `authStore`.

**Admin onboarding wizard** provisions a new association end-to-end: Login (unregistered phone) → `OTP_VERIFICATION` → `ASSOCIATION_REGISTRATION` (name, community type, blocks/villas) → `MAP_CONFIGURATION` (place each block/villa on the map) → `FEATURE_CONFIGURATION` (toggle modules) → `ADMIN_PROFILE` → `ONBOARDING_OTP` → `ONBOARDING_SUCCESS`. Route paths are centralized in `routes/authRoutes.js#AUTH_ROUTES` — use those constants, not hardcoded strings, for anything in this flow. Each step is gated by `routes/OnboardingFlowRoute.jsx`, which redirects to `previousRoute` if `onboardingStore.onboardingStep` (see `data/onboarding.js#ONBOARDING_STEPS`) hasn't reached `minimumStep` yet, and by `routes/AuthFlowRoute.jsx` for the two OTP screens, which check `authFlowState` against an `allowedStates` list. `services/onboardingRegistrationService.js#createAssociationRegistration` assembles the final `association` + `admin` records from the onboarding draft when the wizard completes — this is the seam a real "create association" API call would replace.

**Invite flow (admin adds a resident to an existing association).** Admin → Residents → "Add Resident" creates one user record per phone (`status: 'Invited'`) for the flat and mints an **opaque single-use invite token** (`lib/tokens.js`) with a magic link `…/join/<token>`. `/join/:token` (`pages/Join/JoinPage.jsx`) or the login "invite code" path calls `redeemInvite`, which activates every user of that `apartmentId`, consumes the token, and logs the resident in. The valid/used/expired decision is the pure `lib/invites.js#applyRedeem`. A resident can self-add another number to their flat from their Profile (`addPhoneToApartment`).

**Two parallel dashboards gated by role.** `frontend/src/App.jsx` defines all routes. `ProtectedRoute` (inline in `App.jsx`) redirects to `/login` if `currentUser` is null, and to `/resident` if a `requiredRole` doesn't match. Two independent layout shells:
- `layouts/ResidentLayout.jsx` + `pages/ResidentDashboard/*` — resident pages (home, visitors, complaints, amenities, payments, notices, profile).
- `layouts/AdminLayout.jsx` + `pages/AdminDashboard/*` — admin pages (home, pending, residents, admins, amenities, notices, complaints, maintenance, settings), plus the nested `amenities/:amenityId/*` detail routes described below.

Both render `<Header>` + `<Outlet>` and duplicate their sidebar/nav by design (deliberately separate UIs). An `Admin` can switch between `/admin` and `/resident` from each sidebar; residents cannot reach `/admin`. Login routes by role (`user.role === 'Admin' ? '/admin' : '/resident'`).

**`features/amenities/` is a self-contained vertical-slice module**, structurally different from the rest of the app (which is flat `pages/` + shared `store/slices/`). Everything amenity-specific — `components/`, `constants/`, `hooks/`, `layouts/`, `pages/`, `persistence/`, `services/`, `store/`, `utils/` — lives under this one directory instead of being spread across the top-level folders. Its data flow is layered, not a single Zustand slice:

1. **`persistence/*Persistence.js`** — raw localStorage read/write for one collection (e.g. `amenitiesPersistence.js`), versioned with its own `..._VERSION` key so a shape change can force a reseed instead of crashing on old data. Falls back to an in-memory value when `window` is unavailable.
2. **`services/*Service.js`** — business logic on top of persistence: normalizes records, generates ids (`lib/ids.js`), validates (`utils/validate*.js`), throws plain `Error`s for not-found/invalid input. This is the layer a future REST/Axios call would replace; call signatures are written to match that future contract.
3. **`store/use*Store.js`** — a dedicated Zustand store per sub-domain (`useAmenitiesStore`, `useAmenityBookingsStore`, `useAmenityLedgerStore`, `useAmenityReportsStore`), holding `isLoading`/`error` plus the collection, calling into the service layer and triggering `useAppStore.getState().showToast(...)` / `addActivity(...)` on success — same side-effect convention as the main app.
4. **`hooks/use*.js`** — form/selection logic on top of a store (e.g. `useAmenityForm`, `useBookingTimelineSelection`).
5. **`pages/*.jsx`** and **`components/**/*.jsx`** consume the hooks/stores; nested UI groups (Approvals, Ledger, Reports, Settings, booking modals) live in their own subfolders under `components/`.

Routing: `/admin/amenities/:amenityId` renders `layouts/AmenityDetailLayout.jsx` with tab children `index` (dashboard), `approvals`, `ledger`, `settings`; `/admin/amenities/reports` is lazy-loaded (`React.lazy` + `Suspense` in `App.jsx`) since it's off the main navigation path. **When extending amenities, follow this persistence → service → store → hook → component layering** rather than reaching for an `appStore` slice.

**Toasts and activity feed are global side effects.** Almost every mutating action — in `appStore` slices and in the amenities stores alike — calls `showToast(message, type)` (rendered by `components/common/ToastContainer.jsx`, mounted once at the `App.jsx` root) and `addActivity(text, type)` (feeds the dashboard "recent activity" timeline). Call both when adding an action.

**Shared helpers** live in `frontend/src/lib/`: `genId(prefix)` (`ids.js`), `todayISO()`/`longDate()`/`shortTime()` (`dates.js`), invite tokens (`tokens.js`), redemption logic (`invites.js`). `frontend/src/utils/phone.js` has phone normalization/validation (`normalizePhoneNumber`, `isValidMobileNumber`, `sanitizePhoneInput`) used by both auth paths. Prefer these over re-inlining `Date.now()` / date wrangling / phone regexes; don't add a UUID, date, or phone-validation library.

**Styling** is Tailwind v4 via the `@tailwindcss/vite` plugin (no `tailwind.config.js` — v4 is configured through CSS/Vite). Icons are `lucide-react`. Routing is `react-router-dom` v7. See `docs/DESIGN.md` for the full visual-language spec (color/radius/shadow tables, component recipes) before styling anything new.

## Backend (`backend/`)

A Python **FastAPI** service over **Supabase** — Supabase owns the whole backend (Postgres, Auth, Storage, Realtime); FastAPI is a thin typed API layer in front of it. Not yet consumed by the frontend. Full detail in [backend/README.md](backend/README.md); setup/run/test commands are there. Key conventions:

- **All Supabase access goes through one util:** `backend/app/core/supabase_client.py`. Nothing else calls `create_client`. It exposes three clients by trust level: `get_anon_client()` (RLS, no user), `get_service_client()` (service-role, **bypasses RLS** — privileged ops only), and `get_user_client(token)` (anon client carrying the caller's JWT so **RLS runs as that user** — the default for request-scoped data).
- **Layering:** `api/` (routers + `deps.py` guards) → `services/` (business logic, framework-agnostic) → `repositories/` (data access, always via the util) → Supabase. Domain types/DTOs in `domain/` (`roles.py`, `schemas.py`). Config is env-driven and cached in `config.py`. Follow this layering; keep business logic out of routers.
- **RBAC (`RESIDENT, MANAGER, TECHNICIAN, SECURITY, ADMIN`; ADMIN ⊇ RESIDENT):** role lives on `profiles.role`, is injected into every JWT as a `user_role` claim by a Supabase **access-token hook**, and is enforced in **three layers** — Postgres **RLS**, FastAPI `require_role(...)` guards (`app/api/deps.py`), and the verified `Principal` (`app/core/security.py`). `app/domain/roles.py#role_satisfies` is the single source of truth for role implication (used by guards and tests alike).
- **Auth flows:** login = phone **SMS OTP** (`/api/v1/auth/otp/{request,verify}`, `should_create_user=false`) + refresh (remember-me); registration = admin-initiated invite (`POST /api/v1/admin/invitations`) that returns a one-time **magic link _and_ typable code**, redeemed at `POST /api/v1/auth/redeem` (only hashes stored; single-use via compare-and-set). The pure redeem decision (`invitation_service.evaluate_invitation`) mirrors the frontend's `lib/invites.js#applyRedeem`.
- **SQL** lives in `backend/supabase/migrations/` (`0001` schema, `0002` RLS, `0003` access-token hook) — apply in order and register the hook in the Supabase dashboard.
- **Style:** Google Python conventions — type hints, module/function docstrings, small single-responsibility modules. Lint with `ruff`; pure logic is unit-tested under `backend/tests/` (`pytest`, no network).
