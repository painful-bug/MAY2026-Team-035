# Admin Registration — flow and API contract

**Status:** design of record as of 2026-07-29, following the team decision to authenticate with
**OAuth**. Steps 1–5 describe screens that exist in `frontend/src/`; step 0 and the path chooser are
new build.
**Scope:** administrator registration only — that is, founding a community. The resident join path
is named where the flows diverge and is documented separately.
**Audience:** backend team.

**Companion documents:** [`BACKEND_PLAN.md`](plans/BACKEND_PLAN.md) §6 (auth model),
[`CHANGE_LOG.md`](CHANGE_LOG.md) (why each design artifact changed),
[`erd/homebandhu.dbml`](erd/homebandhu.dbml) (schema), [`class-diagram/`](class-diagram/) (domain
model).

Field-level detail below was read out of `frontend/src/`, not out of
`frontend-documentation.md`. Where the two disagree, this file describes **the code**.

---

## 0. Summary

Administrator registration and community registration are **one workflow** and cannot be separated:
there is no way to create an administrator except by founding a community. The founder authenticates
with an OAuth provider, and the backend then decides what that account means.

Authentication and authorisation stay strictly separate. The provider answers exactly one question —
*who holds this account* — and answers it before any HomeBandhu-specific decision is made. Whether
the account is a member of anything, and of what, is resolved afterwards from our own tables. The
client never asserts a role.

Two properties fall out of this and are worth stating because they were previously things we had to
engineer:

- **Account enumeration is closed by construction.** The registration check happens *after*
  authentication, so there is no unauthenticated probe that distinguishes a known account from an
  unknown one.
- **There is no per-attempt delivery cost**, so rate limiting on the entry path is ordinary abuse
  protection rather than a budget control.

---

## 1. Flow shape

```
/  (Landing)
      │  "Get Started" / "Sign In"
      ▼
  OAuth provider consent  ──►  redirect back to the app
      │
      ▼
  POST /auth/session            ← exchange, set session cookie
      │
      ▼
  registration check  (does this account hold an active membership?)
      │
      ├── yes ──────────────────────────────────►  dashboard for its displayRole
      │
      └── no ──►  /get-started        ← NEW SCREEN: two buttons
                      │
                      ├── "Join a community"    ──►  resident join path   (out of scope here)
                      │
                      └── "Create a community"  ──►  /association-registration   (1/5)
                                                     /map-configuration          (2/5)
                                                     /feature-configuration      (3/5)
                                                     /admin-profile              (4/5)
                                                     review & create             (5/5)
                                                          │
                                                          ▼
                                                     /onboarding-success
                                                          │
                                                          ▼
                                                        /admin
```

### What is already built

| Piece | State |
|---|---|
| Steps 1–5 screens, stepper, back/next, draft persistence | **built** |
| Route guards that stop you skipping ahead (`OnboardingFlowRoute`) | **built** |
| Apartment ⊕ villa exclusivity in the store | **built** |
| Single service seam for the create call | **built** |
| OAuth sign-in | **not built** — no OAuth code exists anywhere in `frontend/src/` |
| `/get-started` chooser | **not built** |

Steps 1–5 are reusable as they stand. §7 lists the specific changes they need.

### How the flow is gated

`OnboardingFlowRoute` ([`routes/OnboardingFlowRoute.jsx`](../frontend/src/routes/OnboardingFlowRoute.jsx))
admits a step when **either** an active registration flow is in progress **or** a draft exists in
`sessionStorage` (`associationName` non-empty and `onboardingStep >= minimumStep`). It also bounces
an already-authenticated Admin to `/admin`.

The second condition means a persisted draft can re-enter the flow without an active client auth
state. That is harmless, because the session is what actually authorises the final call — but it
means **the session must comfortably outlast a slow five-screen form**. Recommend a 60-minute
access-token life for this path or a silent refresh, plus a distinguishable
`401 SESSION_EXPIRED` so the UI can say something useful rather than failing generically.

### Where draft state lives

All five steps write to `useOnboardingStore`
([`store/onboardingStore.js`](../frontend/src/store/onboardingStore.js)), persisted to
**`sessionStorage`** under `homebandhu-admin-onboarding` (`version: 5`, with a `migrate` function).
Steps 1–4 make **no network call**. The community is created in a single call at step 5.

---

## 2. Step 0 — sign in

The user authenticates with the OAuth provider. Supabase Auth handles the provider handshake
(PKCE), so no provider secret lives in our code and no redirect logic is ours to maintain.

```
client:  supabase.auth.signInWithOAuth({ provider, options: { redirectTo } })
         → provider consent → redirect back with a code
         → supabase exchanges the code for a session
```

The client then hands that session to us so the refresh credential can be moved into a cookie the
browser's JavaScript cannot read, per `BACKEND_PLAN.md` §3.7:

```
POST /api/v1/auth/session
  { "accessToken": "…", "refreshToken": "…" }

  → 200
    Set-Cookie: hb_refresh=…; Secure; HttpOnly; SameSite=Lax
    {
      "data": {
        "registered": false,
        "nextStep": "CHOOSE_PATH",
        "redirectTo": "/get-started",
        "identity": {
          "email": "aakash@example.com",
          "emailVerified": true,
          "displayName": "Aakash Deka",
          "avatarUrl": "https://…"
        }
      }
    }
```

For an account that already holds an active membership:

```json
{
  "data": {
    "registered": true,
    "displayRole": "Admin",
    "redirectTo": "/admin",
    "user": { "id": "…", "fullName": "…", "role": "Admin", "communityId": "…" }
  }
}
```

`GET /api/v1/auth/me` returns the same body for an existing session, and is what the app calls on
reload.

### The registration check

`registered` is true when the profile behind this account holds a **community membership with
`status = 'active'`**. Nothing else counts — not an existing profile row, not a pending invitation.
This keeps the check on one predicate that RLS already depends on.

`displayRole` is the projection described in `BACKEND_PLAN.md` §6.6: the API emits the frontend's
existing vocabulary (`Admin | Resident | SecurityManager | Security | Staff`), computed server-side
from the internal `(role, department_kind, rank)` triple, so the router needs no knowledge of our
role model.

### What the identity gives us

| From the provider | Use |
|---|---|
| `sub` (provider user id) | the login credential; stored by Supabase in `auth.identities` |
| verified email | `auth.users.email` — **the identity**, and unique across the platform |
| display name, avatar URL | **suggestions only** — pre-fill step 4, never trusted as final values |

The `AuthenticationProvider` port (`BACKEND_PLAN.md` §6.8) is unchanged by this decision. Its
`VerifiedIdentity` value object was defined to carry *credential holder and nothing else* — no role,
no membership, no community — which is exactly what an OAuth identity yields. The port stays; only
the adapter behind it changes. Nothing outside `app/auth/provider.py` may import the provider SDK.

---

## 3. Step 0.5 — `/get-started`: the path chooser

**New screen. Not implemented.** Shown only to an authenticated account with no active membership.

Two buttons, no fields, no request:

| Button | Goes to | Meaning |
|---|---|---|
| **Join a community** | resident join path | I live somewhere that already uses HomeBandhu |
| **Create a community** | `/association-registration` | I am setting up a new association |

This screen is pure navigation — **it must not send anything to the server**. The choice is not a
claim of authority; it selects which registration flow to start, and each flow is authorised on its
own terms when it submits. A user who picks "Create a community" gains nothing until
`POST /communities/register` succeeds.

A membership-less authenticated session is a real session that holds **no** community scope. RLS
grants it nothing, so it is safe for it to exist while the user decides.

---

## 4. Step 1/5 — `/association-registration`

| Field | Type | Required | Validation |
|---|---|---|---|
| `associationName` | string | yes | trimmed, 3–100 chars (input also carries `maxLength=100`) |
| `communityType` | `'apartment'` \| `'layout_villa'` | yes | defaults to `apartment` |
| `blocks[]` | `{ id: 'block-1', name: 'Block A' }` | ≥ 1 if apartment | **count only** |
| `villas[]` | `{ id: 'villa-1', name: 'Villa 1' }` | ≥ 1 if villa | **count only** |

Caps: **10 blocks**, **50 villas** (`ONBOARDING_CONFIG`). Both arrays always exist in the store; the
community type decides which the UI shows and which the service reads at step 5. Ids are
client-generated sequential slugs (`block-1`, `villa-3`), reused as the map keys in step 2.

**Not validated:** block and villa names are checked for neither blanks nor duplicates. An empty
label reaches step 2 and renders as "Unnamed Block". Server-side this meets
`buildings_community_label_uq` or a blank-label check at step 5 — see §6.5.

**Back** on this step abandons the flow and returns to the start; it is not a navigation backwards.

---

## 5. Step 2/5 — `/map-configuration`

| Field | Type | Required |
|---|---|---|
| `blockLocations` | `{ "block-1": { "x": 24.3312, "y": 41.8890 } }` | every block, if apartment |
| `villaLocations` | `{ "villa-1": { … } }` | every villa, if villa |

`x` and `y` are **percentages (0–100, 4 dp) of a bundled PNG**, computed from
`getBoundingClientRect` in [`MapCard.jsx:3`](../frontend/src/components/onboarding/map/MapCard.jsx#L3).
They are not latitude and longitude and must not be stored as such — see §8.

**This is the only hard gate in the flow:** Next stays disabled until every unit has a marker.

`currentSelectedBlock` / `currentSelectedVilla` auto-advance to the next unplaced unit. They are UI
state and need not reach the server.

---

## 6. Step 3/5 — `/feature-configuration`

| Field | Type | Required |
|---|---|---|
| `enabledModules` | `string[]` of module ids | **no validation at all** |

The **ten** module ids, from
[`data/onboardingModules.js`](../frontend/src/data/onboardingModules.js):

| id | default |
|---|---|
| `resident-management` | on |
| `visitor-management` | on |
| `complaint-management` | on |
| `maintenance-billing` | on |
| `notice-board` | on |
| `amenities-booking` | off |
| `security-gate-management` | off |
| `parking-management` | off |
| `staff-management` | off |
| `community-marketplace` | off |

All ten can be switched off and the step still passes. `sanitizeEnabledModules` de-dupes and drops
unknown ids on rehydrate, so the client self-cleans, but the **server must validate against this
exact list** — it is the authoritative vocabulary. (`frontend-documentation.md` shows a different
set, `["visitors","complaints","amenities","payments"]`, which exists nowhere in the code.)

**Module selection is metadata, not authorisation.** A disabled module hides UI; it must never be
the only thing preventing access to an endpoint.

---

## 7. Step 4/5 — `/admin-profile`

The page states the intent in its own subtitle: *"This administrator will also be registered as the
first resident with association management privileges."*

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `fullName` | string | yes | trimmed, ≥ 3 chars | **pre-fill** from the provider display name |
| `designation` | string | **no** | none | fixed list: President, Secretary, Treasurer, Committee Member, Association Manager, Other |
| `email` | string | yes | `/^[^\s@]+@[^\s@]+\.[^\s@]+$/` | see below — this is now a **contact** address |
| `phone` | string | — | — | currently read-only and sourced from state this design no longer populates — see §9 |
| `unitNumber` | string | yes | non-empty only | free text; label switches "Flat Number" / "Villa Number" by community type |
| `profileImage` | string | no | `file.type.startsWith('image/')` only | base64 data URL, **no size cap** |

**Email now has two distinct meanings and they must not be conflated.** The provider's verified
email is the *identity* and is taken from the token — never from the request body. The email typed
here is a *contact* address for the association and may legitimately differ. The server must ignore
any identity claim in the payload.

`setAdminProfileField` carries a whitelist of exactly four editable fields — `fullName`,
`designation`, `email`, `unitNumber`. `profileImage` has its own setter and is produced by
`FileReader.readAsDataURL`; there is no upload call anywhere, and the uploader's own text reads
*"Nothing will be uploaded yet."*

---

## 8. Step 5/5 — review and create

The final step submits everything gathered in steps 1–4 as **one request**. It is the only step that
calls the API.

The screen is reached at `/onboarding-otp-verification` and needs to be replaced and its route
renamed — see §9. Functionally it is a confirmation step: a summary of what is about to be created
and a single "Create Association" button, which calls `createAssociation()` in
[`createOnboardingCompletionSlice.js`](../frontend/src/store/slices/createOnboardingCompletionSlice.js).
On success the store holds `createdAssociation` + `createdAdmin` and the app navigates to
`/onboarding-success`.

No additional credential is collected here. The user has been authenticated since step 0 and their
session is the authorisation for this call.

---

## 9. The API contract

### 9.1 Request

One call, everything, at step 5.

```
POST /api/v1/communities/register
Authorization: Bearer <access token from step 0>
Content-Type: application/json
```

```jsonc
{
  "community": {
    "name": "Palm Grove Residency",
    "communityType": "apartment"              // | "layout_villa"
  },

  "buildings": [                              // apartment communities only
    { "clientId": "block-1", "label": "Block A", "sortOrder": 0,
      "mapX": 24.3312, "mapY": 41.8890 }
  ],

  "units": [],                                // villa communities only:
                                              // { clientId, label, unitType: "villa", mapX, mapY }

  "enabledModules": [
    "resident-management", "visitor-management", "complaint-management",
    "maintenance-billing", "notice-board"
  ],

  "admin": {
    "fullName": "Aakash Deka",
    "designation": "President",               // may be absent — optional in the UI
    "contactEmail": "office@palmgrove.example",  // contact address, NOT the identity
    "phone": "+919876543210",                 // optional — see §10
    "unitNumber": "A-302",
    "profileImage": "data:image/jpeg;base64,…"   // may be absent
  }
}
```

`buildings` and `units` are mutually exclusive — exactly one is non-empty, decided by
`communityType`. This is the §3.3 exclusivity rule, and the schema makes the mixed case
unrepresentable rather than merely rejected.

**The server must reject any client-supplied `communityId`, `role`, `createdBy`, identity email or
provider id.** Identity comes from the token; authority is the server's to assign.

### 9.2 Where each field lands

Everything below happens inside **one** `register_community(payload jsonb)` transaction.

| Source | Table / column |
|---|---|
| token — provider identity | `auth.users` + `auth.identities` (already created at step 0) |
| token — verified email | `auth.users.email` |
| `community.name` | `communities.name` |
| `community.communityType` | `communities.community_type` — **immutable from this point** |
| `buildings[]` | `buildings` — `label`, `sort_order`, map point |
| `units[]` (villa) | `units` — `unit_label`, `unit_type = 'villa'`, map point |
| `enabledModules` | `community_settings.enabled_modules` |
| `admin.fullName` | `profiles.display_name` |
| `admin.contactEmail` | `profiles.email` **only — never `auth.users.email`** |
| `admin.phone` | `profiles.phone_e164` (nullable — see §10) |
| — | `community_memberships` — `role = 'admin'`, `status = 'active'` |
| `admin.unitNumber` | the admin's own `units` row + `unit_residencies` (`is_primary_contact = true`) |
| `admin.designation` | `committee_positions.designation` |
| `admin.profileImage` | `media_assets` + `profiles.avatar_object_path` |
| — | `communities.active_admin_membership_id`, `audit_events` |

The residency and committee rows are **not optional extras**. They are what makes "the admin is a
committee member and therefore also a resident" true in the data rather than in application logic —
which is what lets the admin use `/resident` with no special case (`BACKEND_PLAN.md` §6.6).

### 9.3 Response

Two screens destructure this directly, so the shape is load-bearing.

```jsonc
{
  "data": {
    "association": {
      "id": "…",
      "name": "Palm Grove Residency",
      "communityType": "apartment",
      "unitType": "Blocks",            // display string — rendered as "Number of {unitType}"
      "unitCount": 3,
      "enabledModules": ["…"],
      "status": "Active"
    },
    "admin": {
      "id": "…",
      "fullName": "Aakash Deka",
      "role": "Admin",                 // must be this exact literal
      "status": "Active"
    },
    "redirectTo": "/admin"
  }
}
```

Consumers:

- `OnboardingSuccessPage` reads `association.name`, `.communityType`, `.unitType`, `.unitCount`,
  `.enabledModules` and `admin.fullName`.
- `ProtectedRoute` compares `admin.role === 'Admin'` — supply the display-role projection, not the
  internal three-axis role.

The current mock also emits `tower`, `flat`, `apartmentId`, `associationId`, `designation` and
`profileImage`. Of those, `apartmentId` is used elsewhere in the app as the flat key.
**`associationId` is written but read nowhere in the codebase**, so `communityId` replaces it
freely. The success screen also renders the founder's phone; with phone now optional, that field
must tolerate a null.

### 9.4 Idempotency

The frontend sends no `Idempotency-Key` and has nowhere to generate or persist one. The button
guards against double-clicks (`nextDisabled={isCreating}`), but a retry after a network timeout
would create a second community.

**Recommended:** derive the key **server-side from the authenticated account id** — one community
per account. This needs no frontend change, is strictly stronger than a client-supplied header
(which a client can vary at will), and aligns with the one-account-one-association rule, so the
second attempt is a natural conflict rather than a silent duplicate.

### 9.5 Error responses

| Code | When |
|---|---|
| `401 SESSION_REQUIRED` / `SESSION_EXPIRED` | no valid session, or it lapsed mid-form |
| `403 EMAIL_NOT_VERIFIED` | the provider did not assert a verified email |
| `409 ALREADY_IN_ANOTHER_COMMUNITY` | this account already holds an active membership (§6.7) |
| `409 COMMUNITY_ALREADY_CREATED` | this account already founded a community |
| `409 DUPLICATE_UNIT_NAME` | two blocks or villas share a label |
| `413 FILE_TOO_LARGE` / `415 UNSUPPORTED_MEDIA_TYPE` | profile image |
| `422 VALIDATION_ERROR` | with nested keys, e.g. `buildings[0].label` |

Because all validation happens at step 5, **any 422 surfaces on the final screen for something typed
four screens earlier.** Keep messages specific enough to be actionable from there, and return the
field path so the UI can eventually deep-link back to the offending step.

---

## 10. Frontend work this design implies

Steps 1–5 exist and are largely reusable. These are the deltas, listed so the frontend team can
scope them. **None has been made** — no file under `frontend/` has been modified.

1. **OAuth sign-in.** No OAuth code exists anywhere in `frontend/src/`. This is new build:
   provider button, redirect handling, session hand-off to `POST /auth/session`, and the
   registered/not-registered branch.
2. **`/get-started` chooser.** New screen, two buttons, no fields.
3. **The step-5 screen must be replaced** with a review-and-create screen, and its route
   (`/onboarding-otp-verification`) renamed to something like `/review-and-create`. The create call
   itself is unchanged.
4. **The step-4 phone field.** It is currently read-only and populated from auth state that this
   design no longer fills, so as written it would render blank and the founder would be recorded
   with no phone number. It needs to become either an editable optional field or be removed. This is
   a product decision: see §11(9).
5. **Step-4 pre-fill.** `fullName` and the avatar should be seeded from the provider identity, with
   the user able to override both.
6. **The entry points.** `/login`, `/admin-otp-verification` and the landing-page links that point
   at them are replaced by the OAuth entry.

---

## 11. Open items for the backend

Items 1–8 predate this decision and remain open. Items 9–12 arise from it.

1. **No flat inventory exists.** Onboarding creates blocks *or* villas and stops. An apartment
   community reaches step 5 with **zero `units` rows**, yet `unit_residencies.unit_id` is `not null`
   and the admin must get a residency. Villa communities are unaffected — the villas *are* the units.
2. **The admin's unit is not bound to anything.** `unitNumber` is free text. The mock derives
   `tower` as `unitNumber.split('-')[0]`, giving `"A"` — which will never match a block labelled
   `"Block A"`. Nothing stops `"Z-9"` in a community with one block.
3. **No postal address is collected anywhere**, although `communities.address_line_1`, `city`,
   `state`, `postal_code` and `country_code` are all `not null` in the ERD, and `PostalAddress`
   marks the same five `{required}` in the class diagram.
4. **Map markers are image percentages, not coordinates.** Storing a 0–100 percentage in
   `latitude numeric(9,6)` is accepted silently and is a type lie that stays invisible until real
   maps arrive. Recommend distinct `map_x` / `map_y` columns.
5. **`timezone` and `default_currency_code` are `not null` and never collected.** Server defaults
   (`Asia/Kolkata`, `INR`).
6. **`designation` is optional in the UI but `committee_positions.designation` is `not null`.**
   Needs a default, or a decision to skip the position when blank.
7. **Base64 image in `sessionStorage`.** A 3 MB photo, inflated ~33% by base64, against a ~5 MB
   quota — the persist middleware throws and the entire draft is lost. Absorbable server-side
   (decode, validate, push to the `profile-avatars` bucket) but the quota risk belongs to the
   frontend.
8. **Late-failing validation.** Everything is checked at step 5, four screens after it was typed.
9. **`profiles.phone_e164` is `not null` and `unique`.** With OAuth, an account may legitimately
   have no phone at all. The column must become nullable, and the unique constraint must tolerate
   nulls (Postgres does this natively — multiple nulls do not collide). The same applies to
   `community_registration_requests.applicant_phone_e164`. **This is a required schema change
   before phase 1.**
10. **Which provider(s)?** Google alone, or Google plus others. Adding a second provider later
    raises identity linking: the same human arriving via a different provider with the same verified
    email must resolve to one account, not two. Supabase supports linking, but the policy is ours to
    set. Decide before launch, because retrofitting a link across existing memberships is painful.
11. **Email uniqueness is now load-bearing and correct.** `auth.users.email` being unique is the
    identity guarantee. The typed contact email must never be written there — see §9.2.
12. **The non-admin login story needs revisiting.** This document covers administrators only, but
    the same entry path will serve every role, and some of them may not have or want a provider
    account on a personal device. That is a product decision, not a backend one, and it is out of
    scope here — but it should not be discovered late.

---

## 12. Source files

| Concern | File |
|---|---|
| Step 1 | [`pages/AssociationRegistration/AssociationRegistrationPage.jsx`](../frontend/src/pages/AssociationRegistration/AssociationRegistrationPage.jsx) |
| Step 2 | [`pages/MapConfiguration/MapConfigurationPage.jsx`](../frontend/src/pages/MapConfiguration/MapConfigurationPage.jsx) |
| Step 3 | [`pages/FeatureConfiguration/FeatureConfigurationPage.jsx`](../frontend/src/pages/FeatureConfiguration/FeatureConfigurationPage.jsx) |
| Step 4 | [`pages/AdminProfile/AdminProfilePage.jsx`](../frontend/src/pages/AdminProfile/AdminProfilePage.jsx) |
| Step 5 | `pages/OnboardingOtp/OnboardingOtpPage.jsx` — **deleted since; it was the OTP screen this document already marked "to be replaced"**. The step is now `pages/OnboardingReview/` |
| Success + dashboard hand-off | [`pages/OnboardingSuccess/OnboardingSuccessPage.jsx`](../frontend/src/pages/OnboardingSuccess/OnboardingSuccessPage.jsx) |
| Draft state, persistence | [`store/onboardingStore.js`](../frontend/src/store/onboardingStore.js) |
| Step-4 fields, editable whitelist | [`store/slices/createOnboardingAdminProfileSlice.js`](../frontend/src/store/slices/createOnboardingAdminProfileSlice.js) |
| Step-5 submit | [`store/slices/createOnboardingCompletionSlice.js`](../frontend/src/store/slices/createOnboardingCompletionSlice.js) |
| **The single API seam** | [`services/onboardingRegistrationService.js`](../frontend/src/services/onboardingRegistrationService.js) |
| Route guards | [`routes/OnboardingFlowRoute.jsx`](../frontend/src/routes/OnboardingFlowRoute.jsx). `routes/AuthFlowRoute.jsx` was deleted with the OTP flow; the auth paths now live in [`routes/authRoutes.js`](../frontend/src/routes/authRoutes.js) |
| Session state | [`store/authStore.js`](../frontend/src/store/authStore.js) |
| Constants, caps, module list | [`data/onboarding.js`](../frontend/src/data/onboarding.js), [`data/onboardingModules.js`](../frontend/src/data/onboardingModules.js), [`data/adminDesignations.js`](../frontend/src/data/adminDesignations.js) |
| Validators | [`utils/onboarding.js`](../frontend/src/utils/onboarding.js), [`utils/adminProfile.js`](../frontend/src/utils/adminProfile.js) |

**The frontend calls no endpoints today.** There is no `fetch`, no `axios`, no HTTP client in
`package.json` and no `VITE_API_*` variable. `services/onboardingRegistrationService.js` is the one
seam this whole flow passes through, and its own comment names it as such: replacing its body
requires no change in the store or the pages.
