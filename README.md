# HomeBandhu

Residential society / apartment management app for residents and association
administrators. This repository is an npm-workspaces monorepo.

## What is included

- Separate resident and admin dashboards with role-based routing
- Visitors, complaints, notices, maintenance, payments, and resident management
- Amenity booking, approvals, ledger, reports, and configuration flows
- Association onboarding and single-use resident invite links
- Browser-persisted demo data with cross-tab synchronization

```
.
├── frontend/   # React 19 + Vite + Tailwind v4 SPA (all app code)
└── backend/    # reserved — no server yet
```

The frontend has **no backend**. Domain state lives in a Zustand store
persisted to browser storage, which also gives it realtime cross-tab sync
(a change in one tab shows up in others without a reload). See
`frontend/src/store/`.

## Getting started

```bash
npm install          # once, from repo root — installs the frontend workspace
npm run dev          # start Vite dev server
npm run build        # production build
npm run preview      # preview the build
npm run lint         # oxlint
```

Open the local URL printed by Vite after running `npm run dev`. All root scripts
proxy to the `frontend` workspace (`-w frontend`).

## Demo logins

- Resident: phone `9876543210`
- Admin: phone `9999988888`

OTP is simulated — any 4–6 digit code works. Admins can switch between the
admin and resident dashboards from the sidebar.

## Development notes

- App routes are defined in `frontend/src/App.jsx`.
- Seed data lives in `frontend/src/data/`; shared application state lives in
  `frontend/src/store/`.
- There is no configured test runner yet. Invite-token and redemption logic can
  be checked with `node frontend/src/lib/selfcheck.mjs`.
- Use the root `package-lock.json` with npm; avoid mixing package managers.
