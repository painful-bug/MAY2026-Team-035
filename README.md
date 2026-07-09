# HomeBandhu

Residential society / apartment management app. npm-workspaces monorepo.

```
.
├── frontend/   # React 19 + Vite + Tailwind v4 SPA (all app code)
└── backend/    # reserved — no server yet
```

The frontend has **no backend**. Domain state lives in a Zustand store
persisted to browser storage, which also gives it realtime cross-tab sync
(a change in one tab shows up in others without a reload). See
`frontend/src/store/`.

## Run

```bash
npm install          # once, from repo root — installs the frontend workspace
npm run dev          # start Vite dev server
npm run build        # production build
npm run preview      # preview the build
npm run lint         # oxlint
```

All scripts proxy to the `frontend` workspace (`-w frontend`).

## Demo logins

- Resident: phone `9876543210`
- Admin: phone `9999988888`

OTP is simulated — any 4–6 digit code works. Admins can switch between the
admin and resident dashboards from the sidebar.
