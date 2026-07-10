# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"HomeBandhu" — a residential society/apartment management app. React 19 + Vite + Tailwind CSS v4. There is **no backend**: all data lives in a Zustand store seeded from static arrays in `frontend/src/data/`. State is persisted to browser storage, so it survives reloads and syncs across tabs.

Monorepo (npm workspaces): all app code is in `frontend/`; `backend/` is an empty placeholder for a future server.

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

**Single Zustand store, no backend, persisted + cross-tab synced.** The data layer is `frontend/src/store/`, not a React context (there is no provider — Zustand is provider-less):

- **`appStore.js`** — every domain collection (`users`, `invitations`, `pendingRequests`, `complaints`, `notices`, `visitors`, `bookings`, `payments`, `amenities`, `activities`) plus their actions. Composed from `store/slices/create*Slice.js`, one slice per domain, each a `(set, get) => ({ <collection>, ...actions })` creator seeded from `src/data/*.js`. Persisted to **localStorage** via the `persist` middleware; `partialize` allowlists the collections and omits transient UI (`toasts`, `searchQuery`).
- **`authStore.js`** — `currentUser` + `login`/`logout`/`setCurrentUser`. Persisted to **sessionStorage** so each browser tab keeps its own session (a resident tab and an admin tab stay independently logged in while sharing the same domain data).
- **`sync.js`** (`initCrossTabSync`, called once in `main.jsx`) — a `storage`-event listener that calls `useAppStore.persist.rehydrate()` so a change in one tab re-renders the others with no reload. This is the "realtime hydration" the PRD asks for and the fix for the reported cross-tab bug.
- **`useApp.js`** — a `useApp()` facade that merges both stores into the object shape the old React context exposed, so pages didn't have to change. For a hot component, subscribe with a scoped selector instead, e.g. `useAppStore(s => s.complaints)`.

Cross-slice actions reach siblings via `get()` (e.g. `acceptRequest` writes users + payments + pendingRequests in one `set`). Cross-store access is at call time via `getState()` (e.g. `login` reads `useAppStore.getState().users`; slices that need the logged-in user read `useAuthStore.getState().currentUser`). appStore and authStore import each other — this circular import is safe because nothing crosses stores during module evaluation, only inside action bodies.

When adding a stateful feature: add a seed array to `src/data/`, add a `create<Domain>Slice.js`, compose it in `appStore.js`, and (if it needs the same keys as before) it's already exposed through `useApp()`. Each mutating action should call `get().showToast(...)` and `get().addActivity(...)` like the rest.

**Auth is simulated.** `login(phone, otp)` does not check the OTP — it matches the phone against `users` (plus two demo shortcut numbers: resident `9876543210` = u1, admin `9999988888` = u2). "Logged in" is just `currentUser` being non-null in `authStore`.

**Invite flow (admin adds a resident).** Admin → Residents → "Add Resident" creates one user record per phone (`status: 'Invited'`) for the flat and mints an **opaque single-use invite token** (`lib/tokens.js`) with a magic link `…/join/<token>`. `/join/:token` (`pages/Join/JoinPage.jsx`) or the login "invite code" path calls `redeemInvite`, which activates every user of that `apartmentId`, consumes the token, and logs the resident in. The valid/used/expired decision is the pure `lib/invites.js#applyRedeem`. A resident can self-add another number to their flat from their Profile (`addPhoneToApartment`).

**Two parallel dashboards gated by role.** `frontend/src/App.jsx` defines all routes. `ProtectedRoute` (inline in `App.jsx`) redirects to `/login` if `currentUser` is null, and to `/resident` if a `requiredRole` doesn't match. Two independent layout shells:
- `layouts/ResidentLayout.jsx` + `pages/ResidentDashboard/*` — resident pages (home, visitors, complaints, amenities, payments, notices, profile).
- `layouts/AdminLayout.jsx` + `pages/AdminDashboard/*` — admin pages (home, pending, residents, admins, amenities, notices, complaints, maintenance, settings).

Both render `<Header>` + `<Outlet>` and duplicate their sidebar/nav by design (deliberately separate UIs). An `Admin` can switch between `/admin` and `/resident` from each sidebar; residents cannot reach `/admin`. Login routes by role (`user.role === 'Admin' ? '/admin' : '/resident'`).

**Toasts and activity feed are global side effects.** Almost every mutating action calls `showToast(message, type)` (rendered by `components/common/ToastContainer.jsx`, mounted once at the `App.jsx` root) and `addActivity(text, type)` (feeds the dashboard "recent activity" timeline). Call both when adding an action.

**Shared helpers** live in `frontend/src/lib/`: `genId(prefix)` (`ids.js`), `todayISO()`/`longDate()`/`shortTime()` (`dates.js`), invite tokens (`tokens.js`), redemption logic (`invites.js`). Prefer these over re-inlining `Date.now()` / date wrangling; don't add a UUID or date library.

**Styling** is Tailwind v4 via the `@tailwindcss/vite` plugin (no `tailwind.config.js` — v4 is configured through CSS/Vite). Icons are `lucide-react`. Routing is `react-router-dom` v7.
