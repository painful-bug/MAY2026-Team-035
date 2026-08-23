# API ↔ code ↔ spec mapper

**Verified on the `services-and-security` branch on 2026-08-11.** **179 API operations across 150
paths**, plus 4 of FastAPI's own docs endpoints (`/docs`, `/docs/oauth2-redirect`, `/redoc`,
`/openapi.json`), which the spec does not carry. All 179 appear in [`openapi.yaml`](openapi.yaml);
the spec documents nothing that the code does not serve. 860 tests pass.

*(This line read **99 operations, 686 tests, `main` @ `98d557a`** when the file was created on
2026-08-08. The tables below have been kept current endpoint by endpoint since; this header and the
counts in §5 and §6.2 had not, which is exactly the drift §7 exists to make visible.)*

*(**Re-counted 2026-08-20 on `live-app-fixes`: 199 operations across 168 paths**, all 199 in the
spec, `api_map_scan.py` reporting the same **20** findings and all 24 stories agreeing. The
operation count above is left standing as the record of what 2026-08-11 verified — the drift is the
point of §7 — but read 199/168 as today's number. **The test total is not re-verified**; only
`tests/test_openapi_spec.py` was run in this pass, and a count nobody re-ran is exactly what the
paragraph above is about.)*

*(**Re-counted 2026-08-22 on `live-app-fixes`: 203 operations across 172 paths**, all 203 in the
spec, `api_map_scan.py` still reporting the same **20** findings and all 24 stories agreeing — the
supervisor-triage pair added neither a finding nor a story gap. §3's tables were regenerated in the
same pass, which moved roughly a hundred `API.md` line references that the new §18 subsection had
pushed down: that is [`regen_mapper.py`](../backend/scripts/regen_mapper.py) doing the job it was
written for, and not a change to any row's meaning.)*

*(**Re-counted 2026-08-23 on `live-app-fixes`: 209 operations across 178 paths**, all 209 in the
spec, `api_map_scan.py` still reporting the same **20** findings and all 24 stories agreeing — the
open-jobs board pair (`GET /worker/open-jobs`, `POST /worker/jobs/{id}/claim`) added neither a
finding nor a story gap. §3's tables were regenerated in the same pass, which moved the `API.md`
line references the two new endpoint sections had pushed down.)*

*(**Re-counted 2026-08-23 on `live-app-fixes`, second pass: 210 operations across 179 paths**, all
210 in the spec, `api_map_scan.py` still reporting the same **20** findings and all 24 stories
agreeing — `POST /complaints/{id}/schedule-time` (ruling F1, the resident sets the time) added
neither a finding nor a story gap; it tags `US-2.8`, which was already served. §3's tables were
**not** regenerated in this pass: the one new row sits under a `####` heading, which
[`regen_mapper.py`](../backend/scripts/regen_mapper.py) does not auto-link, so it was hand-filled
beside its two siblings rather than moving a hundred unrelated `API.md` line references to add one.)*

This file answers one question in one place: **for a given backend source file, which endpoints does
it implement, and where does each one live in the spec and in the reference docs?** It is the third
leg of the documentation set —

| File | What it is | How it is maintained |
|---|---|---|
| [`openapi.yaml`](openapi.yaml) | The machine contract. Shapes, status codes, traceability | **Generated**, never hand-edited |
| [`API.md`](API.md) | The prose contract. Why a rule exists, what a guard protects | Hand-written |
| **`api_yaml_mapper.md`** (this file) | The index tying source files to both of the above | **§3's tables are generated** by [`regen_mapper.py`](../backend/scripts/regen_mapper.py); the prose around them is hand-written, and [`api_map_scan.py`](../backend/scripts/api_map_scan.py) says when it has fallen behind |

---

## 1. How to read a row

Every operation appears exactly once, under the file that registers it.

```
| `POST /api/v1/notices` | `create_notice` :26 | `create_notice_api_v1_notices_post` | 201 NoticeCreated | § 12.1 … (API.md:2327) |
   └── the route             └── handler + line   └── the yaml anchor                  └── success body  └── the prose section
```

**The mapping mechanism is `operationId`.** It is unique across the whole spec, FastAPI derives it
from the handler name and the path, and it is a plain string — so it is greppable from any of the
three files:

```bash
grep -n "create_notice_api_v1_notices_post" docs/openapi.yaml
```

That lands on the operation, and the block under it carries `summary`, `description`, `tags`,
`requestBody`, every `responses` entry, and `x-user-stories`. Going the other way — spec back to code
— strip the `_api_v1_…` suffix and the remainder is the Python handler name.

**The API.md column has three values:**

- **§ `heading`** — a dedicated reference section names this operation.
- **mention only — § …** — the operation is covered by a section-level table or by prose, but has no
  heading of its own. This is deliberate for auth (§3 documents the whole family as tables) and for
  Web Push (§5.3 covers three endpoints under one heading). It is *not* deliberate anywhere else.
- **missing** — API.md does not document this operation at all. See §5.

**The success-schema column** shows the status code and the component name the spec returns.
`free-form object` means the spec says `{}` or `additionalProperties: true` — a client generated from
it gets an untyped blob. Those are listed in §5.

---

## 2. Layer chain per router

Each router table is preceded by the service, repository and schema modules that operation family
flows through, so a change in a repository can be traced forward to the endpoints and the spec
sections it can break. Repositories are listed transitively — routers import services, services
import repositories.

---

## 3. The tables

### `backend/app/main.py`

App factory: mounts `api_router` at `/api/v1`, installs the exception handlers, sets
`Cache-Control: no-store, private` on `/api/v1/auth/*` except paths ending `/methods`, and defines
one route inline.

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /health` | `health` :108 | `health_health_get` | 200 inline | § `GET /health` (API.md:353) |

### `backend/app/api/v1/routers/access_requests.py`

**Layers** — service `access_request_service` · repositories `access_requests_repository`,
`profiles_repository` · schemas `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/access-requests` | `create_access_request` :22 | `create_access_request_api_v1_access_requests_post` | 201 AccessRequestResponse | mention only — § 6. People (API.md:931) |
| `GET /api/v1/access-requests/mine` | `my_access_requests` :35 | `my_access_requests_api_v1_access_requests_mine_get` | 200 AccessRequestListResponse | **missing** |
| `POST /api/v1/access-requests/{request_id}/withdraw` | `withdraw_access_request` :42 | `withdraw_access_request_api_v1_access_requests__request_id__withdraw_post` | 200 AccessRequestResponse | **missing** |
| `GET /api/v1/admin/access-requests` | `admin_access_requests` :54 | `admin_access_requests_api_v1_admin_access_requests_get` | 200 AccessRequestListResponse | mention only — § 6. People (API.md:931) |
| `POST /api/v1/admin/access-requests/{request_id}/approve` | `approve_access_request` :63 | `approve_access_request_api_v1_admin_access_requests__request_id__approve_post` | 200 free-form object | **missing** |
| `POST /api/v1/admin/access-requests/{request_id}/blacklist` | `blacklist_access_request` :87 | `blacklist_access_request_api_v1_admin_access_requests__request_id__blacklist_post` | 200 free-form object | **missing** |
| `POST /api/v1/admin/access-requests/{request_id}/reject` | `reject_access_request` :75 | `reject_access_request_api_v1_admin_access_requests__request_id__reject_post` | 200 free-form object | **missing** |

### `backend/app/api/v1/routers/amenities.py`

**Layers** — service `amenities_service` · repositories `amenities_repository`, `tenancy_repository`
· schemas `domain/amenity_schemas.py`, `domain/common_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/amenities/{amenity_id}/approvals` | `list_approvals` :194 | `list_approvals_api_v1_amenities__amenity_id__approvals_get` | 200 Page_ApprovalRequest_ | § `GET /api/v1/amenities/{amenityId}/approvals` (API.md:2278) |
| `POST /api/v1/amenities/{amenity_id}/blocks` | `block_slot` :173 | `block_slot_api_v1_amenities__amenity_id__blocks_post` | 201 BookingSummary | § `POST /api/v1/amenities/{amenityId}/blocks` (API.md:2251) |
| `GET /api/v1/amenities/{amenity_id}/bookings` | `list_amenity_bookings` :66 | `list_amenity_bookings_api_v1_amenities__amenity_id__bookings_get` | 200 Page_BookingSummary_ | § `GET /api/v1/amenities/{amenityId}/bookings` (API.md:2097) |
| `POST /api/v1/amenities/{amenity_id}/bookings` | `create_admin_booking` :113 | `create_admin_booking_api_v1_amenities__amenity_id__bookings_post` | 201 BookingSummary | § `POST /api/v1/amenities/{amenityId}/bookings` (API.md:2174) |
| `POST /api/v1/amenities/{amenity_id}/bookings/request` | `request_booking` :141 | `request_booking_api_v1_amenities__amenity_id__bookings_request_post` | 201 Page_BookingSummary_ | § `POST /api/v1/amenities/{amenityId}/bookings/request` (API.md:2213) |
| `GET /api/v1/amenities/{amenity_id}/ledger` | `list_ledger` :334 | `list_ledger_api_v1_amenities__amenity_id__ledger_get` | 200 Page_LedgerTransaction_ | § `GET /api/v1/amenities/{amenityId}/ledger` (API.md:2402) |
| `GET /api/v1/amenities/{amenity_id}/ledger/summary` | `get_ledger_summary` :378 | `get_ledger_summary_api_v1_amenities__amenity_id__ledger_summary_get` | 200 LedgerSummary | § `GET /api/v1/amenities/{amenityId}/ledger/summary` (API.md:2491) |
| `POST /api/v1/amenity-bookings/cancel` | `cancel_bookings` :277 | `cancel_bookings_api_v1_amenity_bookings_cancel_post` | 200 MessageResult | § `POST /api/v1/amenity-bookings/cancel` (API.md:2348) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/charges` | `add_charge` :474 | `add_charge_api_v1_amenity_bookings__occurrence_id__charges_post` | 201 LedgerTransaction | § `POST /api/v1/amenity-bookings/{occurrenceId}/charges` (API.md:2592) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/damage` | `deduct_damage` :449 | `deduct_damage_api_v1_amenity_bookings__occurrence_id__damage_post` | 201 LedgerTransaction | § `POST /api/v1/amenity-bookings/{occurrenceId}/damage` (API.md:2571) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/force-cancel` | `force_cancel_booking` :305 | `force_cancel_booking_api_v1_amenity_bookings__occurrence_id__force_cancel_post` | 200 BookingSummary | § `POST /api/v1/amenity-bookings/{occurrenceId}/force-cancel` (API.md:2382) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/payments` | `record_payment` :400 | `record_payment_api_v1_amenity_bookings__occurrence_id__payments_post` | 201 LedgerTransaction | § `POST /api/v1/amenity-bookings/{occurrenceId}/payments` (API.md:2517) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/refund` | `refund_deposit` :424 | `refund_deposit_api_v1_amenity_bookings__occurrence_id__refund_post` | 201 LedgerTransaction | § `POST /api/v1/amenity-bookings/{occurrenceId}/refund` (API.md:2547) |
| `POST /api/v1/amenity-bookings/{series_id}/approve` | `approve_booking` :234 | `approve_booking_api_v1_amenity_bookings__series_id__approve_post` | 200 Page_BookingSummary_ | § `POST /api/v1/amenity-bookings/{seriesId}/approve` (API.md:2312) |
| `POST /api/v1/amenity-bookings/{series_id}/reject` | `reject_booking` :254 | `reject_booking_api_v1_amenity_bookings__series_id__reject_post` | 200 Page_BookingSummary_ | § `POST /api/v1/amenity-bookings/{seriesId}/reject` (API.md:2327) |
| `GET /api/v1/amenity-reports` | `get_report` :503 | `get_report_api_v1_amenity_reports_get` | 200 AmenityReport | § `GET /api/v1/amenity-reports` (API.md:2612) |

> `POST …/bookings/request`, `…/approve` and `…/reject` returning `Page[BookingSummary]` is
> deliberate, not a mis-declared model: one request covers several days and the handler returns every
> day it touched. The docstrings say so.

### `backend/app/api/v1/routers/auth.py`

**Layers** — service `auth_service` · repository `profiles_repository` · schemas `domain/schemas.py`

Owned by the auth workstream. The spec's error codes and descriptions for these operations come from
[`api_annotations.py`](../backend/scripts/api_annotations.py), not from the handlers.

**"Remember me" is spelled differently on each of the three paths, and none of them is in a response
schema** — so the mapper rows below cannot show it. `POST /password/sign-in` takes it as the body
field `remember_me`; `GET /oauth/{provider}/start` (and its `/google/start` alias) as the query
parameter `remember`, which is then stored in the signed PKCE transaction cookie and read back by the
callback; `POST /refresh` reads it from the `remember` cookie so rotation does not change it, and
`POST /logout` clears that cookie. All four converge on one function,
`app/core/web_session.py::establish_session(..., persist=)`, which is the only place the refresh
cookie's `Max-Age` is decided. See API.md § 1.2 for the cookie contract.

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/auth/csrf` | `csrf` :111 | `csrf_api_v1_auth_csrf_get` | 200 MessageResponse | mention only — § 3.1 (API.md:374) |
| `POST /api/v1/auth/email/resend` | `resend_email` :196 | `resend_email_api_v1_auth_email_resend_post` | 200 MessageResponse | mention only — § 3.3 Email and password (API.md:398) |
| `POST /api/v1/auth/email/verify` | `verify_email` :185 | `verify_email_api_v1_auth_email_verify_post` | 200 MessageResponse | mention only — § 3.3 Email and password (API.md:398) |
| `GET /api/v1/auth/google/callback` | `google_callback` :149 | `google_callback_api_v1_auth_google_callback_get` | 307 free-form object | mention only — § 3.2 Google OAuth (API.md:381) |
| `GET /api/v1/auth/google/start` | `google_start` :144 | `google_start_api_v1_auth_google_start_get` | 307 free-form object | mention only — § 3.2 Google OAuth (API.md:381) |
| `POST /api/v1/auth/logout` | `logout` :281 | `logout_api_v1_auth_logout_post` | 200 MessageResponse | mention only — § 3.5 Session lifecycle (API.md:442) |
| `GET /api/v1/auth/methods` | `auth_methods` :102 | `auth_methods_api_v1_auth_methods_get` | **200 free-form object** | mention only — § 3. Authentication (API.md:364) |
| `GET /api/v1/auth/oauth/{provider}/callback` | `oauth_callback` :129 | `oauth_callback_api_v1_auth_oauth__provider__callback_get` | 307 free-form object | mention only — § 3.2 Google OAuth (API.md:381) |
| `GET /api/v1/auth/oauth/{provider}/start` | `oauth_start` :117 | `oauth_start_api_v1_auth_oauth__provider__start_get` | 307 free-form object | mention only — § 3.2 Google OAuth (API.md:381) |
| `POST /api/v1/auth/password/reset/complete` | `password_reset_complete` :234 | `password_reset_complete_api_v1_auth_password_reset_complete_post` | 200 MessageResponse | mention only — § 3.4 Password recovery (API.md:429) |
| `POST /api/v1/auth/password/reset/request` | `password_reset_request` :218 | `password_reset_request_api_v1_auth_password_reset_request_post` | 200 MessageResponse | mention only — § 3.4 Password recovery (API.md:429) |
| `POST /api/v1/auth/password/reset/verify` | `password_reset_verify` :227 | `password_reset_verify_api_v1_auth_password_reset_verify_post` | 200 MessageResponse | mention only — § 3.4 Password recovery (API.md:429) |
| `POST /api/v1/auth/password/sign-in` | `password_sign_in` :175 | `password_sign_in_api_v1_auth_password_sign_in_post` | 200 MessageResponse | mention only — § 3.3 Email and password (API.md:398) |
| `POST /api/v1/auth/password/sign-up` | `password_sign_up` :154 | `password_sign_up_api_v1_auth_password_sign_up_post` | 200 MessageResponse | mention only — § 3.3 Email and password (API.md:398) |
| `POST /api/v1/auth/refresh` | `refresh` :269 | `refresh_api_v1_auth_refresh_post` | 200 MessageResponse | mention only — § 3.5 Session lifecycle (API.md:442) |
| `GET /api/v1/auth/session` | `session` :245 | `session_api_v1_auth_session_get` | 200 SessionContext | mention only — § 3.5 Session lifecycle (API.md:442) |

### `backend/app/api/v1/routers/communities.py`

**Layers** — service `community_directory_service` · repository `communities_repository` · schemas
`domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/communities/admin/units` | `list_admin_units` :27 | `list_admin_units_api_v1_communities_admin_units_get` | 200 CommunityUnitListResponse | **missing** |
| `GET /api/v1/communities/search` | `search_communities` :18 | `search_communities_api_v1_communities_search_get` | 200 CommunitySearchResponse | **missing** |

### `backend/app/api/v1/routers/complaints.py`

**Layers** — service `complaints_service` · repositories `complaints_repository`,
`people_repository`, `tenancy_repository` · schemas `domain/complaint_schemas.py`,
`domain/common_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/complaints/admin-raise` | `admin_raise_complaint` :66 | `admin_raise_complaint_api_v1_complaints_admin_raise_post` | 201 AdminComplaintRaised | § `POST /api/v1/complaints/admin-raise` (API.md:1173) |
| `GET /api/v1/complaints/staff/complaints/{complaint_id}` | `staff_complaint_detail` :37 | `staff_complaint_detail_api_v1_complaints_staff_complaints__complaint_id__get` | 200 StaffComplaintDetail | § `GET /api/v1/complaints/staff/complaints/{complaintId}` |
| `PATCH /api/v1/complaints/{complaint_id}` | `update_complaint` :124 | `update_complaint_api_v1_complaints__complaint_id__patch` | 200 MessageResult | § `PATCH /api/v1/complaints/{complaintId}` (API.md:1256) |
| `POST /api/v1/complaints/{complaint_id}/comments` | `add_comment` :151 | `add_comment_api_v1_complaints__complaint_id__comments_post` | 201 MessageResult | § `POST /api/v1/complaints/{complaintId}/comments` (API.md:1288) |

> **`POST /complaints/admin-raise` is on this router and not on `resident_complaints.py`**, added
> 2026-08-20. It is an admin write — `require_admin` plus the router-level CSRF dependency — and it
> belongs with the other two. The path is a literal segment under the `/complaints` prefix and is
> collision-free: the resident router's `GET /complaints/{complaint_id}` would swallow `admin-raise`
> on a `GET`, and this is a `POST`, for which no `/complaints/{id}` route exists.
>
> **The two request modes are one optional field**, `forMembershipId`, and `complaints.raised_via` is
> derived by the RPC rather than accepted from the client — a body that could carry both could carry
> them contradicting each other. `admin_raise_complaint`
> (`20260820150000_admin_raised_complaints.sql`) re-checks what `require_admin` already concluded,
> because the function is `security definer` and callable by any authenticated role; an endpoint
> guard is not a database guard.

### `backend/app/api/v1/routers/dashboard.py`

**Layers** — service `dashboard_service` · repository `dashboard_repository` · schemas
`domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/dashboard/amenities` | `create_amenity` :54 | `create_amenity_api_v1_dashboard_amenities_post` | **200 free-form object** | mention only — § 16.6 (API.md:4245) |
| `PUT /api/v1/dashboard/amenities/{amenity_id}` | `update_amenity` :67 | `update_amenity_api_v1_dashboard_amenities__amenity_id__put` | **200 free-form object** | **missing** |
| `DELETE /api/v1/dashboard/amenities/{amenity_id}` | `delete_amenity` :81 | `delete_amenity_api_v1_dashboard_amenities__amenity_id__delete` | **200 free-form object** | **missing** |
| `GET /api/v1/dashboard/events` | `dashboard_events` :32 | `dashboard_events_api_v1_dashboard_events_get` | 200 `text/event-stream` | mention only — § 5.1 (API.md:684) |
| `GET /api/v1/dashboard/snapshot` | `get_dashboard_snapshot` :17 | `get_dashboard_snapshot_api_v1_dashboard_snapshot_get` | 200 DashboardSnapshot | mention only — § 5 (API.md:657) |

### `backend/app/api/v1/routers/geo.py`

**Layers** — service `geocoding_service` · repository *none — the store is an in-process TTL cache
and the source is an external HTTP API* · schemas `domain/geo_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/geo/reverse` | `reverse_place` :70 | `reverse_place_api_v1_geo_reverse_get` | 200 GeoPlace | § `GET /api/v1/geo/reverse` (API.md:8211) |
| `GET /api/v1/geo/search` | `search_places` :31 | `search_places_api_v1_geo_search_get` | 200 array of GeoPlace | § `GET /api/v1/geo/search` (API.md:8182) |

### `backend/app/api/v1/routers/departments.py`

**Layers** — service `departments_service` · repositories `departments_repository`,
`tenancy_repository` · schemas `domain/department_schemas.py`, `domain/common_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/departments` | `list_departments` :55 | `list_departments_api_v1_departments_get` | 200 Page_DepartmentDetail_ | § `GET /api/v1/departments` (API.md:1514) |
| `POST /api/v1/departments` | `create_department` :95 | `create_department_api_v1_departments_post` | 201 DepartmentDetail | § `POST /api/v1/departments` (API.md:1630) |
| `GET /api/v1/departments/{department_id}` | `get_department` :117 | `get_department_api_v1_departments__department_id__get` | 200 DepartmentDetail | § `GET /api/v1/departments/{departmentId}` (API.md:1674) |
| `PATCH /api/v1/departments/{department_id}` | `update_department` :131 | `update_department_api_v1_departments__department_id__patch` | 200 DepartmentDetail | § `PATCH /api/v1/departments/{departmentId}` (API.md:1717) |
| `DELETE /api/v1/departments/{department_id}` | `delete_department` :159 | `delete_department_api_v1_departments__department_id__delete` | 200 MessageResult | § `DELETE /api/v1/departments/{departmentId}` (API.md:1746) |

### `backend/app/api/v1/routers/events.py`

**Layers** — service `dashboard_service` · repository `dashboard_repository` · schemas
`domain/schemas.py` · also `core/realtime.py` (the in-process fan-out hub)

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/events` | `events` :78 | `events_api_v1_events_get` | 200 `text/event-stream` | § 5.1 Live updates — `GET /events` (API.md:684) |

> The `text/event-stream` content type with no schema is **correct and intentional** — a client
> generated from a JSON schema would try to decode a live stream. `SSE_RESPONSES` in this file carries
> the comment explaining it.

### `backend/app/api/v1/routers/invitations.py`

**Layers** — services `invitation_service`, `auth_service` · repositories `invitations_repository`,
`memberships_repository`, `profiles_repository` · schemas `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/admin/invitations` | `create_invitation` :20 | `create_invitation_api_v1_admin_invitations_post` | 200 InvitationCreated | § `POST /api/v1/admin/invitations` (API.md:596) |
| `POST /api/v1/invitations/prepare` | `prepare_invitation` :29 | `prepare_invitation_api_v1_invitations_prepare_post` | 200 MessageResponse | § `POST /api/v1/invitations/prepare` (API.md:635) |
| `POST /api/v1/invitations/redeem` | `redeem_invitation` :36 | `redeem_invitation_api_v1_invitations_redeem_post` | 200 MessageResponse | § `POST /api/v1/invitations/redeem` (API.md:645) |

### `backend/app/api/v1/routers/money.py`

**Layers** — service `money_service` · repositories `money_repository`, `tenancy_repository` ·
schemas `domain/money_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/billing-settings` | `get_billing_settings` :98 | `get_billing_settings_api_v1_billing_settings_get` | 200 BillingSettings | § `GET /api/v1/billing-settings` (API.md:1881) |
| `PUT /api/v1/billing-settings` | `update_billing_settings` :115 | `update_billing_settings_api_v1_billing_settings_put` | 200 BillingSettings | § `PUT /api/v1/billing-settings` (API.md:1933) |
| `POST /api/v1/invoices` | `create_invoice` :46 | `create_invoice_api_v1_invoices_post` | 201 InvoiceDetail | § `POST /api/v1/invoices` (API.md:1799) |
| `POST /api/v1/invoices/{invoice_id}/payments` | `record_payment` :70 | `record_payment_api_v1_invoices__invoice_id__payments_post` | 201 InvoiceDetail | § `POST /api/v1/invoices/{invoiceId}/payments` (API.md:1840) |

### `backend/app/api/v1/routers/notices.py`

**Layers** — service `notices_service` · repository `notices_repository` · schemas
`domain/notice_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/notices` | `create_notice` :26 | `create_notice_api_v1_notices_post` | 201 NoticeCreated | § 12.1 `POST /notices` (API.md:2927) |

### `backend/app/api/v1/routers/notifications.py`

**Layers** — service `notifications_service` · repository `notifications_repository` · schemas
`domain/notification_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/notifications` | `list_notifications` :31 | `list_notifications_api_v1_notifications_get` | 200 NotificationFeed | § `GET /api/v1/notifications` (API.md:785) |
| `POST /api/v1/notifications/read-all` | `mark_all_notifications_read` :100 | `mark_all_notifications_read_api_v1_notifications_read_all_post` | 200 NotificationReadResult | § `POST /api/v1/notifications/read-all` (API.md:833) |
| `POST /api/v1/notifications/{notification_id}/read` | `mark_notification_read` :74 | `mark_notification_read_api_v1_notifications__notification_id__read_post` | 200 NotificationReadResult | § `POST /api/v1/notifications/{notificationId}/read` (API.md:824) |

### `backend/app/api/v1/routers/onboarding.py`

**Layers** — services `onboarding_service`, `auth_service` · repository `profiles_repository` ·
schemas `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/onboarding/community` | `create_community` :12 | `create_community_api_v1_onboarding_community_post` | 200 CommunityOnboardingResponse | mention only — § 16.6 (API.md:4245) |

### `backend/app/api/v1/routers/people.py`

**Layers** — service `people_service` · repositories `people_repository`, `tenancy_repository` ·
schemas `domain/people_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/admins` | `promote_admin` :27 | `promote_admin_api_v1_admins_post` | 200 AdminSummary | § 12.2 `POST /admins` (API.md:2982) |

### `backend/app/api/v1/routers/push.py`

**Layers** — service `push_service` · repository `push_repository` · schemas
`domain/notification_schemas.py`, `domain/schemas.py` · also `core/push.py`, `core/push_config.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/push/subscriptions` | `subscribe` :58 | `subscribe_api_v1_push_subscriptions_post` | 200 PushSubscriptionResult | § 5.3 Web Push (API.md:845) |
| `POST /api/v1/push/subscriptions/unregister` | `unsubscribe` :89 | `unsubscribe_api_v1_push_subscriptions_unregister_post` | 200 PushSubscriptionResult | § 5.3 Web Push (API.md:845) |
| `GET /api/v1/push/vapid-key` | `vapid_key` :33 | `vapid_key_api_v1_push_vapid_key_get` | 200 VapidPublicKey | § 5.3 Web Push (API.md:845) |

> `unregister` is a POST to a sub-path rather than `DELETE /push/subscriptions` with a body, because
> RFC 9110 gives no semantics to a body on `DELETE`. `_check_request_bodies` in the exporter fails the
> build if anyone reintroduces one.

### `backend/app/api/v1/routers/resident_amenities.py`

**Layers** — service `resident_amenities_service` · repository `resident_amenities_repository` ·
schemas `domain/resident_amenity_schemas.py`, `domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/amenities/available` | `list_available_amenities` :30 | `list_available_amenities_api_v1_amenities_available_get` | 200 Page_BookableAmenity_ | § `GET /api/v1/amenities/available` (API.md:2025) |

### `backend/app/api/v1/routers/resident_complaints.py`

**Layers** — service `resident_complaints_service` · repository `resident_complaints_repository` ·
schemas `domain/resident_complaint_schemas.py`, `domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/complaints` | `list_my_complaints` :67 | `list_my_complaints_api_v1_complaints_get` | 200 Page_ComplaintSummary_ | § `GET /api/v1/complaints` (API.md:1325) |
| `POST /api/v1/complaints` | `raise_complaint` :112 | `raise_complaint_api_v1_complaints_post` | 201 ComplaintDetail | § `POST /api/v1/complaints` (API.md:1360) |
| `GET /api/v1/complaints/{complaint_id}` | `get_complaint` :151 | `get_complaint_api_v1_complaints__complaint_id__get` | 200 ComplaintDetail | § `GET /api/v1/complaints/{complaintId}` (API.md:1415) |
| `POST /api/v1/complaints/{complaint_id}/cancel` | `cancel_complaint_work` :184 | `cancel_complaint_work_api_v1_complaints__complaint_id__cancel_post` | 200 ComplaintDetail | § Complaint Engine v2 additions (API.md:55) |
| `POST /api/v1/complaints/{complaint_id}/read` | `mark_complaint_read` :262 | `mark_complaint_read_api_v1_complaints__complaint_id__read_post` | 200 MessageResult | § `POST …/read` |
| `POST /api/v1/complaints/{complaint_id}/reopen` | `reopen_complaint` :201 | `reopen_complaint_api_v1_complaints__complaint_id__reopen_post` | 200 ComplaintDetail | § `POST …/reopen` |
| `POST /api/v1/complaints/{complaint_id}/resolution` | `confirm_resolution` :232 | `confirm_resolution_api_v1_complaints__complaint_id__resolution_post` | 200 ComplaintDetail | § `POST …/resolution` |

> **Four of these seven carry `require_resident_capability` since 2026-08-20** — `POST /complaints`,
> `/cancel`, `/reopen`, `/resolution` — and the guard is a **widening for five routes and a narrowing
> for one**. Widening: resident-ness is now an active `unit_residencies` row rather than
> `role == 'resident'`, so an admin who owns a flat holds the verbs on their own home. Narrowing:
> `POST /complaints` previously required only an active membership, so a flat-less `worker`,
> `security` or `manager` could file onto a resident complaint list; it now answers the same `403`
> `community_role_required`. **No path, method, body or response model moved**, so
> `export_openapi.py --check` is byte-identical on all four and only the prose in `API.md` §7.2
> records it — the same blind spot as the `0041` guard move logged in §7.
>
> **`list_mine` and `get_mine` in `resident_complaints_repository` also gained
> `.eq("raised_via", "resident")`.** A complaint an admin raised about the building is owned by their
> membership and would otherwise surface on their own resident list. Nothing in the wire shape
> changed; the rows returned did.

### `backend/app/api/v1/routers/resident_home.py`

**Layers** — service `resident_home_service` · repository `resident_home_repository` · schemas
`domain/resident_home_schemas.py`, `domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/directory/contacts` | `list_contacts` :111 | `list_contacts_api_v1_directory_contacts_get` | 200 array of ManagementContact | § `GET /api/v1/directory/contacts` (API.md:3441) |
| `GET /api/v1/me/household` | `get_household` :61 | `get_household_api_v1_me_household_get` | 200 array of HouseholdMember | § `GET /api/v1/me/household` (API.md:3409) |
| `POST /api/v1/me/household/phones` | `add_household_phone` :85 | `add_household_phone_api_v1_me_household_phones_post` | 200 array of HouseholdMember | § `POST /api/v1/me/household/phones` (API.md:3422) |
| `GET /api/v1/notices` | `list_notices` :31 | `list_notices_api_v1_notices_get` | 200 Page_Notice_ | § `GET /api/v1/notices` (API.md:3396) |

### `backend/app/api/v1/routers/resident_money.py`

**Layers** — service `resident_money_service` (+ `payment_simulator`) · repository
`resident_money_repository` · schemas `domain/resident_money_schemas.py`,
`domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/amenity-bookings/mine` | `list_my_bookings` :119 | `list_my_bookings_api_v1_amenity_bookings_mine_get` | 200 Page_ResidentBooking_ | § `GET /api/v1/amenity-bookings/mine` (API.md:3366) |
| `POST /api/v1/amenity-bookings/{booking_id}/pay` | `pay_booking` :148 | `pay_booking_api_v1_amenity_bookings__booking_id__pay_post` | 200 PaymentOutcome | § `POST /api/v1/amenity-bookings/{bookingId}/pay` (API.md:3375) |
| `GET /api/v1/invoices/mine` | `list_my_invoices` :38 | `list_my_invoices_api_v1_invoices_mine_get` | 200 Page_ResidentInvoice_ | § `GET /api/v1/invoices/mine` (API.md:3313) |
| `POST /api/v1/invoices/{invoice_id}/pay` | `pay_invoice` :76 | `pay_invoice_api_v1_invoices__invoice_id__pay_post` | 200 PaymentOutcome | § `POST /api/v1/invoices/{invoiceId}/pay` (API.md:3338) |

### `backend/app/api/v1/routers/resident_snapshot.py`

**Layers** — service `resident_snapshot_service` (fans out to the other resident services) · schemas
`domain/resident_snapshot_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/resident/snapshot` | `resident_snapshot` :28 | `resident_snapshot_api_v1_resident_snapshot_get` | 200 ResidentSnapshot | § `GET /api/v1/resident/snapshot` (API.md:3480) |

### `backend/app/api/v1/routers/resident_visitor_passes.py`

**Layers** — service `resident_visitor_passes_service` · repository
`resident_visitor_passes_repository` · schemas `domain/resident_visitor_schemas.py`,
`domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/visitor-passes` | `list_my_visitor_passes` :34 | `list_my_visitor_passes_api_v1_visitor_passes_get` | 200 Page_VisitorPass_ | § `GET /api/v1/visitor-passes` (API.md:3091) |
| `POST /api/v1/visitor-passes` | `create_visitor_pass` :69 | `create_visitor_pass_api_v1_visitor_passes_post` | 201 VisitorPassCreated | § `POST /api/v1/visitor-passes` (API.md:3109) |
| `GET /api/v1/visitor-passes/{pass_id}` | `get_visitor_pass` :101 | `get_visitor_pass_api_v1_visitor_passes__pass_id__get` | 200 VisitorPass | § `GET /api/v1/visitor-passes/{passId}` (API.md:3158) |
| `POST /api/v1/visitor-passes/{pass_id}/approve` | `approve_visitor_pass` :123 | `approve_visitor_pass_api_v1_visitor_passes__pass_id__approve_post` | 200 VisitorPass | § `…/approve` · `/reject` |
| `POST /api/v1/visitor-passes/{pass_id}/cancel` | `cancel_visitor_pass` :172 | `cancel_visitor_pass_api_v1_visitor_passes__pass_id__cancel_post` | 200 VisitorPass | § `POST …/cancel` |
| `POST /api/v1/visitor-passes/{pass_id}/reject` | `reject_visitor_pass` :153 | `reject_visitor_pass_api_v1_visitor_passes__pass_id__reject_post` | 200 VisitorPass | § `…/approve` · `/reject` |

### `backend/app/api/v1/routers/service_providers.py`

**Layers** — service `service_providers_service` · repository `service_providers_repository` ·
schemas `domain/service_provider_schemas.py`, `domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/service-providers` | `register` :100 | `register_api_v1_service_providers_post` | 201 ServiceProviderProfile | § `POST /api/v1/service-providers` (API.md:4739) |
| `GET /api/v1/service-providers/me` | `get_mine` :126 | `get_mine_api_v1_service_providers_me_get` | 200 ServiceProviderProfile | § `GET /api/v1/service-providers/me` (API.md:4788) |
| `PATCH /api/v1/service-providers/me` | `update_mine` :149 | `update_mine_api_v1_service_providers_me_patch` | 200 ServiceProviderProfile | § `PATCH /api/v1/service-providers/me` (API.md:4820) |
| `PATCH /api/v1/service-providers/me/availability` | `set_availability` :255 | `set_availability_api_v1_service_providers_me_availability_patch` | 200 AvailabilityResult | § `PATCH …/availability` |
| `PUT /api/v1/service-providers/me/skills` | `set_skills` :230 | `set_skills_api_v1_service_providers_me_skills_put` | 200 SkillsSavedResult | § `PUT /api/v1/service-providers/me/skills` (API.md:4846) |
| `GET /api/v1/service-providers/{provider_id}` | `get_candidate` :194 | `get_candidate_api_v1_service_providers__provider_id__get` | 200 CandidateProfile | **missing** |
| `GET /api/v1/skills` | `list_skills` :46 | `list_skills_api_v1_skills_get` | 200 array of Skill | § `GET /api/v1/skills` (API.md:4558) |

> **The only router in this table that declares no membership dependency.** Every other row in this
> document resolves an active `community_memberships` row before the handler runs. A service person
> who has registered but been hired nowhere holds none, so requiring one would refuse them exactly
> the screens that let them apply for work. Authorization is not absent — it moved into the three
> SECURITY DEFINER RPCs, which resolve the caller from `auth.uid()`, and into `service_providers`
> carrying a read policy and no write policy at all.

> `GET /api/v1/skills` returns a bare array rather than a `Page`, the only collection on this API
> that does. It is twelve rows of seeded reference data; an envelope around a constant would be
> ceremony, and §1.6's one-shape rule is about *collections that grow*.

### `backend/app/api/v1/routers/worker_communities.py`

**Layers** — service `hiring_service` · repositories `hiring_repository`,
`service_providers_repository` · schemas `domain/hiring_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/worker/applications` | `list_my_applications` :97 | `list_my_applications_api_v1_worker_applications_get` | 200 array of ServiceApplication | § `GET /api/v1/worker/applications` (API.md:5060) |
| `POST /api/v1/worker/applications` | `apply` :125 | `apply_api_v1_worker_applications_post` | 201 ServiceApplication | § `POST /api/v1/worker/applications` (API.md:5076) |
| `DELETE /api/v1/worker/applications/{application_id}` | `withdraw` :151 | `withdraw_api_v1_worker_applications__application_id__delete` | 200 ServiceApplication | § `DELETE …/{applicationId}` |
| `POST /api/v1/worker/applications/{application_id}/decision` | `decide_invitation` :175 | `decide_invitation_api_v1_worker_applications__application_id__decision_post` | 200 ServiceApplication | § `POST …/{applicationId}/decision` |
| `GET /api/v1/worker/communities` | `list_my_communities` :43 | `list_my_communities_api_v1_worker_communities_get` | 200 array of ServiceEngagement | § `GET /api/v1/worker/communities` (API.md:4996) |
| `GET /api/v1/worker/communities/search` | `search_communities` :69 | `search_communities_api_v1_worker_communities_search_get` | 200 array of ServiceableCommunity | § `GET …/communities/search` |
| `POST /api/v1/worker/communities/{staff_id}/departure` | `request_departure` :203 | `request_departure_api_v1_worker_communities__staff_id__departure_post` | 201 StaffDeparture | § `POST …/{staffId}/departure` |
| `DELETE /api/v1/worker/communities/{staff_id}/departure` | `cancel_departure` :246 | `cancel_departure_api_v1_worker_communities__staff_id__departure_delete` | 200 MessageResult | § `DELETE …/{staffId}/departure` |

> **The second router declaring no membership dependency**, and for the same reason as
> `service_providers.py` above: this is the surface a service person uses *because* nobody has hired
> them yet. Nothing here takes a community id from the caller — the two searches and the applications
> list are all scoped to the caller's own provider row, resolved from `auth.uid()` inside the RPCs
> and the RLS policy — so there is no id in a request body that could widen what a caller sees.

> `DELETE` returns `200` with the withdrawn row rather than `204`. Nothing is deleted: `withdrawn` is
> a status, the row stays on the list the screen is showing, and the negotiation remains readable by
> both sides.

### `backend/app/api/v1/routers/worker_jobs.py`

**Layers** — service `worker_service` · repositories `worker_repository`,
`service_providers_repository`, `hiring_repository`, `notifications_repository` ·
schemas `domain/worker_schemas.py`, `domain/hiring_schemas.py`,
`domain/service_provider_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/worker/jobs` | `list_jobs` :128 | `list_jobs_api_v1_worker_jobs_get` | 200 array of WorkerJob | § `GET /api/v1/worker/jobs` (API.md:6808) |
| `GET /api/v1/worker/jobs/{work_order_id}` | `get_job` :164 | `get_job_api_v1_worker_jobs__work_order_id__get` | 200 WorkerJobDetail | § `GET …/jobs/{workOrderId}` |
| `POST /api/v1/worker/jobs/{work_order_id}/accept` | `accept_job` :190 | `accept_job_api_v1_worker_jobs__work_order_id__accept_post` | 200 WorkerJob | § `POST …/accept` |
| `POST /api/v1/worker/jobs/{work_order_id}/claim` | `claim_job` :223 | `claim_job_api_v1_worker_jobs__work_order_id__claim_post` | 200 WorkerJob | § `POST …/claim` |
| `POST /api/v1/worker/jobs/{work_order_id}/complete` | `complete_job` :312 | `complete_job_api_v1_worker_jobs__work_order_id__complete_post` | 200 WorkerJob | § `POST …/complete` |
| `POST /api/v1/worker/jobs/{work_order_id}/decline` | `decline_job` :257 | `decline_job_api_v1_worker_jobs__work_order_id__decline_post` | 200 WorkerJob | § `POST …/decline` |
| `POST /api/v1/worker/jobs/{work_order_id}/start` | `start_job` :291 | `start_job_api_v1_worker_jobs__work_order_id__start_post` | 200 WorkerJob | § `POST …/start` |
| `POST /api/v1/worker/jobs/{work_order_id}/unable` | `report_job_failure` :341 | `report_job_failure_api_v1_worker_jobs__work_order_id__unable_post` | 200 WorkerJob | § `POST …/unable` |
| `GET /api/v1/worker/open-jobs` | `list_open_jobs` :95 | `list_open_jobs_api_v1_worker_open_jobs_get` | 200 array of OpenJob | § `GET /api/v1/worker/open-jobs` (API.md:6857) |
| `GET /api/v1/worker/snapshot` | `worker_snapshot` :53 | `worker_snapshot_api_v1_worker_snapshot_get` | 200 WorkerSnapshot | § `GET /api/v1/worker/snapshot` (API.md:6750) |

> **The third router declaring no membership dependency, and the first where that is a correction
> rather than a convenience.** `require_membership_role` reads the role off the caller's *default*
> membership; this surface is deliberately cross-community, so that guard would refuse a plumber who
> lives in one society and works in three others. The rule these routes actually need —
> `is_own_staff_assignment` (`0036` §4) — is applied by `my_worker_job` and by all five verb RPCs.
> See `plans/SERVICE_OPERATIONS_PROGRESS.md` §4.16.

> Every refusal here is `404` rather than `403`, including on the writes. A job the caller holds no
> assignment on does not exist as far as this router is concerned, and a `403` would confirm the id.

> `GET /worker/snapshot` is the only aggregate in the API that answers `200` for a caller with no
> profile at all: a null `provider` **is** the registration empty state. `GET
> /service-providers/me` still `404`s for the same caller, because the question there is different.

### `backend/app/api/v1/routers/worker_schedule.py`

**Layers** — service `worker_service` · repository `worker_repository` ·
schemas `domain/worker_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/worker/availability-rules` | `list_availability_rules` :152 | `list_availability_rules_api_v1_worker_availability_rules_get` | 200 array of AvailabilityRule | § `GET …/availability-rules` |
| `PUT /api/v1/worker/availability-rules` | `set_availability_rules` :174 | `set_availability_rules_api_v1_worker_availability_rules_put` | 200 array of AvailabilityRule | § `GET …/availability-rules` |
| `GET /api/v1/worker/calendar` | `get_calendar` :40 | `get_calendar_api_v1_worker_calendar_get` | 200 array of CalendarEntry | § `GET /api/v1/worker/calendar` (API.md:7068) |
| `GET /api/v1/worker/unavailability` | `list_unavailability` :72 | `list_unavailability_api_v1_worker_unavailability_get` | 200 array of UnavailabilityBlock | § `GET …/unavailability` |
| `POST /api/v1/worker/unavailability` | `add_unavailability` :100 | `add_unavailability_api_v1_worker_unavailability_post` | 201 UnavailabilityBlock | § `GET …/unavailability` |
| `DELETE /api/v1/worker/unavailability/{block_id}` | `delete_unavailability` :130 | `delete_unavailability_api_v1_worker_unavailability__block_id__delete` | 204 no body | § `GET …/unavailability` |

> `GET /worker/calendar` is the one operation in this file with **no view of its own**. It merges
> `my_worker_job` and `my_worker_unavailability` in the service, because both are already views with
> their own definition of *mine* and a SQL union would be a third place for that to drift.

> Three operations share one API.md subsection each rather than getting their own, which is the
> documented exception this file's §5.3 allows for CRUD triples on one resource: the leave trio and
> the availability pair are each one screen and one rule stated once.

### `backend/app/api/v1/routers/department_hiring.py`

**Layers** — service `hiring_service` · repository `hiring_repository` ·
schemas `domain/hiring_schemas.py`, `domain/common_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/departments/{department_id}/applications` | `list_applications` :58 | `list_applications_api_v1_departments__department_id__applications_get` | 200 array of ServiceApplication | § `GET …/applications` |
| `POST /api/v1/departments/{department_id}/applications/{application_id}/decide` | `decide` :158 | `decide_api_v1_departments__department_id__applications__application_id__decide_post` | 200 ServiceApplication | § `POST …/decide` |
| `POST /api/v1/departments/{department_id}/blacklist` | `blacklist` :229 | `blacklist_api_v1_departments__department_id__blacklist_post` | 201 MessageResult | § `POST …/blacklist` |
| `GET /api/v1/departments/{department_id}/candidates` | `list_candidates` :85 | `list_candidates_api_v1_departments__department_id__candidates_get` | 200 array of HireableProvider | § `GET …/candidates` |
| `GET /api/v1/departments/{department_id}/departures` | `list_departures` :275 | `list_departures_api_v1_departments__department_id__departures_get` | 200 array of StaffDeparture | § `GET …/departures` |
| `POST /api/v1/departments/{department_id}/departures` | `open_departure` :329 | `open_departure_api_v1_departments__department_id__departures_post` | 201 StaffDeparture | § `POST …/departures` |
| `GET /api/v1/departments/{department_id}/departures/{departure_id}` | `get_departure` :302 | `get_departure_api_v1_departments__department_id__departures__departure_id__get` | 200 StaffDepartureDetail | § `GET …/departures/{departureId}` |
| `GET /api/v1/departments/{department_id}/departures/{departure_id}/coverage` | `get_departure_coverage` :505 | `get_departure_coverage_api_v1_departments__department_id__departures__departure_id__coverage_get` | 200 array of CoverageItem | § `GET …/coverage` |
| `POST /api/v1/departments/{department_id}/departures/{departure_id}/decide` | `decide_departure` :406 | `decide_departure_api_v1_departments__department_id__departures__departure_id__decide_post` | 200 StaffDeparture | § `POST …/decide` |
| `POST /api/v1/departments/{department_id}/departures/{departure_id}/reassign` | `reassign_item` :368 | `reassign_item_api_v1_departments__department_id__departures__departure_id__reassign_post` | 200 MessageResult | § `POST …/reassign` |
| `POST /api/v1/departments/{department_id}/invitations` | `invite` :122 | `invite_api_v1_departments__department_id__invitations_post` | 201 ServiceApplication | § `POST …/invitations` |
| `POST /api/v1/departments/{department_id}/members/{staff_id}/remove` | `remove_member` :196 | `remove_member_api_v1_departments__department_id__members__staff_id__remove_post` | 200 MessageResult | § `POST …/remove` |
| `GET /api/v1/departments/{department_id}/staff-invitations` | `list_staff_invitations` :551 | `list_staff_invitations_api_v1_departments__department_id__staff_invitations_get` | 200 array of StaffInvitation | **missing** |
| `POST /api/v1/departments/{department_id}/staff-invitations` | `invite_staff_member` :580 | `invite_staff_member_api_v1_departments__department_id__staff_invitations_post` | 201 StaffInvitation | **missing** |
| `PATCH /api/v1/departments/{department_id}/staff-invitations/{invitation_id}` | `update_staff_invitation` :617 | `update_staff_invitation_api_v1_departments__department_id__staff_invitations__invitation_id__patch` | 200 StaffInvitation | **missing** |
| `DELETE /api/v1/departments/{department_id}/staff-invitations/{invitation_id}` | `revoke_staff_invitation` :661 | `revoke_staff_invitation_api_v1_departments__department_id__staff_invitations__invitation_id__delete` | 200 MessageResult | **missing** |
| `GET /api/v1/departments/{department_id}/staff/{staff_id}` | `get_staff_member` :442 | `get_staff_member_api_v1_departments__department_id__staff__staff_id__get` | 200 StaffMemberDetail | § `GET …/staff/{staffId}` |
| `GET /api/v1/departments/{department_id}/staff/{staff_id}/schedule` | `get_staff_schedule` :469 | `get_staff_schedule_api_v1_departments__department_id__staff__staff_id__schedule_get` | 200 array of ScheduleItem | § `GET …/schedule` |

> **The router guard on this table is deliberately the weaker of two.** `require_admin_or_manager`
> asks whether the caller is an admin or manager *somewhere*, resolved from their default membership;
> it cannot ask about the department in the path, because that department's community is not known
> until something reads it. The real check is `can_manage_department(uuid)` in `0035`, applied by
> every RPC here and by the policy behind every read. A manager of one community calling these routes
> against another community's department passes the router guard and is refused by Postgres.

> `POST …/members/{staffId}/remove` is not a `DELETE`, and both halves of that are deliberate.
> Nothing is deleted — the roster row is deactivated, because complaints record staff by name and a
> deleted row turns a past assignment into an unexplained string (`0019` A7). And `reason` is a note
> one person writes about another which reaches them in a notification: `DELETE` cannot carry a body,
> and a query parameter would put it in every access log on the way.

### `backend/app/api/v1/routers/conversations.py`

**Layers** — service `conversations_service` · repository `conversations_repository` ·
schemas `domain/conversation_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/conversations` | `list_conversations` :41 | `list_conversations_api_v1_conversations_get` | 200 array of Conversation | § `GET /api/v1/conversations` (API.md:6089) |
| `POST /api/v1/conversations` | `open_conversation` :69 | `open_conversation_api_v1_conversations_post` | 201 ConversationThread | § `POST /api/v1/conversations` (API.md:6122) |
| `GET /api/v1/conversations/{conversation_id}` | `get_conversation` :99 | `get_conversation_api_v1_conversations__conversation_id__get` | 200 ConversationThread | § `GET …/{conversationId}` |
| `POST /api/v1/conversations/{conversation_id}/messages` | `post_message` :124 | `post_message_api_v1_conversations__conversation_id__messages_post` | 201 ConversationMessage | § `POST …/messages` |

> **The only router on this API with no role guard at all**, and the one place where that is the
> design rather than an oversight. The two routers above bracket the choice: identity-only where the
> caller may hold no membership, `admin`-or-`manager` where every path names a department. A
> conversation belongs to one department *and* one provider, so participation is a property of the
> row — there is no role a router could check that would answer it. `is_conversation_participant`
> (`0038` §3) is the single definition, called by both read policies and both write RPCs.

> **The status codes are asymmetric on purpose.** A thread the caller is not in is absent from the
> list, a `404` on the read, and a `403` on the write. A `403` on the read would confirm that the
> thread exists, making a department's conversations with every other provider enumerable by walking
> ids; the write can afford `403` because the caller has already named a thread they can see.

> `POST /api/v1/conversations` is an upsert and always answers `201`, including when the thread
> already existed. That is what the unique constraint on `(department_id, service_provider_id)` buys:
> no read-then-write, no thread-creation step for a client to remember, and two managers pressing
> "Message" simultaneously landing in the same conversation rather than two half-conversations.

> No notification is emitted here and none is planned before Step 6.
> `notifications.recipient_membership_id` is `not null`, and the provider a manager most needs to
> reach — an invited one, not yet hired — holds no membership in that community. Same wall as the
> invitation in `0035`, recorded in the same words rather than discovered twice.

### `backend/app/api/v1/routers/messages.py`

**Layers** — service `messages_service` · repository `messages_repository` ·
schemas `domain/message_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/messages/recipients` | `list_recipients` :33 | `list_recipients_api_v1_messages_recipients_get` | 200 array of DmRecipient | §20 `GET /api/v1/messages/recipients` (API.md:8036) |
| `GET /api/v1/messages/threads` | `list_threads` :59 | `list_threads_api_v1_messages_threads_get` | 200 array of DmThread | §20 `GET /api/v1/messages/threads` (API.md:8036) |
| `POST /api/v1/messages/threads` | `open_thread` :78 | `open_thread_api_v1_messages_threads_post` | 201 DmThreadDetail | §20 `POST /api/v1/messages/threads` (API.md:8036) |
| `GET /api/v1/messages/threads/{thread_id}` | `get_thread` :104 | `get_thread_api_v1_messages_threads__thread_id__get` | 200 DmThreadDetail | §20 `GET …/{threadId}` (API.md:8036) |
| `POST /api/v1/messages/threads/{thread_id}/messages` | `post_message` :128 | `post_message_api_v1_messages_threads__thread_id__messages_post` | 201 DmMessage | §20 `POST …/messages` (API.md:8036) |

> **Identity-only, the `conversations.py` posture, for the widened reason:** the chat dock mounts on
> every portal (the 2026-08-10 ruling), so there is no role a router could check. `dm_pair_allowed`
> (`0046`) is the single rule behind both the recipients directory and the open, and the RLS read
> policies are the mailbox's scoping. The lock — a work-order thread refusing writes after the job
> ends — surfaces as the `409` on the message post and nowhere else.

### `backend/app/api/v1/routers/work_orders.py`

**Layers** — service `work_orders_service` · repository `work_orders_repository` ·
schemas `domain/work_order_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/complaints/{complaint_id}/work-orders` | `list_complaint_work_orders` :100 | `list_complaint_work_orders_api_v1_complaints__complaint_id__work_orders_get` | 200 array of WorkOrder | § `GET …/work-orders` |
| `POST /api/v1/complaints/{complaint_id}/work-orders` | `create_work_order` :56 | `create_work_order_api_v1_complaints__complaint_id__work_orders_post` | 201 WorkOrder | § `POST …/work-orders` |
| `GET /api/v1/departments/{department_id}/work-orders` | `list_department_work_orders` :118 | `list_department_work_orders_api_v1_departments__department_id__work_orders_get` | 200 array of WorkOrder | § `GET /api/v1/departments/{departmentId}/work-orders` (API.md:6379) |
| `GET /api/v1/work-orders/{work_order_id}` | `get_work_order` :142 | `get_work_order_api_v1_work_orders__work_order_id__get` | 200 WorkOrderDetail | § `GET /api/v1/work-orders/{workOrderId}` (API.md:6397) |
| `PATCH /api/v1/work-orders/{work_order_id}` | `update_work_order` :182 | `update_work_order_api_v1_work_orders__work_order_id__patch` | 200 WorkOrder | § `PATCH /api/v1/work-orders/{workOrderId}` (API.md:6440) |
| `POST /api/v1/work-orders/{work_order_id}/assign` | `assign_work_order` :208 | `assign_work_order_api_v1_work_orders__work_order_id__assign_post` | 200 WorkOrderDetail | § `POST …/assign` |
| `POST /api/v1/work-orders/{work_order_id}/cancel` | `cancel_work_order` :280 | `cancel_work_order_api_v1_work_orders__work_order_id__cancel_post` | 200 WorkOrder | § `POST …/cancel` |
| `GET /api/v1/work-orders/{work_order_id}/candidates` | `work_order_candidates` :167 | `work_order_candidates_api_v1_work_orders__work_order_id__candidates_get` | 200 array of Candidate | § Complaint Engine v2 additions (API.md:55) |
| `POST /api/v1/work-orders/{work_order_id}/reschedule` | `reschedule_work_order` :254 | `reschedule_work_order_api_v1_work_orders__work_order_id__reschedule_post` | 200 WorkOrderDetail | § `POST …/reschedule` |

> **The role guard is coarse by construction, and the file says so.** A department supervisor holds a
> `worker` membership with the `supervisor` *rank* on their roster row — `0035` settled that rank and
> role are different things — so `require_membership_role("admin", "manager", "worker", "security")`
> is the narrowest filter that admits every legitimate caller. It exists to turn a signed-in resident
> poking at ids into a `403` before any query runs. `can_supervise_department(uuid)` (`0036` §4) is
> the boundary, and every RPC on this surface applies it.

> **`/assign` answers to two RPCs since 2026-08-22, chosen by one flag.** `force: false` (the
> default, and the whole existing surface unchanged) is `assign_work_order` — an offer the worker may
> decline. `force: true` is `force_assign_work_order` (`20260822170000` §6), the dispatch engine's own
> forced mechanics with the picking removed and a supervisor's guard added. The branch is in
> `work_orders_service.assign` and not in SQL: "ask this person" and "send this person" are different
> decisions, and one function that did either depending on a flag would have two sets of refusals
> sharing one name.

> **Three routes exist because three writes each carry a rule the `PATCH` would skip.** `/assign`
> books a worker and is where `work_order_assignments_no_overlap` bites; `/reschedule` moves the
> booking with the job and re-checks the same constraint; `/cancel` withdraws the assignment so the
> hour is freed. The `PATCH` model has no `status` and no time field at all — the absence is the
> mechanism, not a validation rule that could be relaxed later by accident.

> **A double-booking is refused twice and answers `409` both times.** `assign_work_order` raises
> `HB409` naming the worker, which reads; the exclusion constraint raises `23P01`, which does not.
> `app/core/pg_errors.py` gained a `23P01` row in this step so the second is a `409` rather than a
> bare `400` — the same answer as `23505`, because it is the same kind of answer: somebody else has
> that already.

> **`in_progress`, `completed` and `failed` are in the schema and unreachable from this router.**
> They are the worker's transitions and arrive with the worker portal. Their presence in
> `work_orders_status_check` is a vocabulary declared once rather than a constraint edited twice.

### `backend/app/api/v1/routers/resident_scheduling.py`

**Layers** — service `work_orders_service` (shared with the router above) ·
repository `work_orders_repository` · schemas `domain/work_order_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/complaints/{complaint_id}/schedule` | `respond_to_schedule` :97 | `respond_to_schedule_api_v1_complaints__complaint_id__schedule_post` | 200 ScheduleRequest | § `POST …/schedule` |
| `POST /api/v1/complaints/{complaint_id}/schedule-time` | `set_schedule_time` :137 | `set_schedule_time_api_v1_complaints__complaint_id__schedule_time_post` | 200 ScheduleRequest | § `POST …/schedule-time` |
| `GET /api/v1/complaints/{complaint_id}/schedule-request` | `get_schedule_request` :56 | `get_schedule_request_api_v1_complaints__complaint_id__schedule_request_get` | 200 ScheduleRequest | § `GET …/schedule-request` |

> **Three routes now, and the third is the 2026-08-23 ruling F1.** `schedule` answers a question the
> association asked; `schedule-time` answers one it did not ask, because it stopped guessing an hour
> for somebody else's home. The two are not interchangeable and each refuses the other's jobs in
> words — the discriminator is `scheduled_start_at`, surfaced on the read as `mode`, and both modes
> are `awaiting_resident` because the status vocabulary is a closed CHECK.

> **Two routers, one service, and that is deliberate.** Splitting the service would put the two sides
> of one state machine in two files, and the transition `awaiting_resident → offered` would be
> written in one and read in the other. The routers differ because the *guards* differ; the state
> machine does not.

> **Neither route takes a work-order id.** The job is resolved from the complaint — newest live one —
> so naming somebody else's is not expressible rather than merely refused. It also means the resident
> never has to have read an id to answer a question that was put to them.

> **Resident-only on both, including the read.** The precedent is `resident_complaints.py`, which
> reserves reopening and confirming a resolution to the resident for the same reason: an admin
> answering on somebody's behalf is a record that says something untrue. Staff read the same row
> through `GET /work-orders/{id}`, which is a wider projection.
>
> **Since 2026-08-20 that is `require_resident_capability`, not `require_membership_role("resident")`**
> (`app/api/deps.py`, router-level on both routes). Resident-ness is an active `unit_residencies`
> row, so an administrator who owns a flat can answer a visit proposed to their own home; the role
> column never recorded that fact. **No wire change** — same `403`, same `community_role_required`
> code, same message — so `--check` sees nothing here, which is the class of change §6.2 step 1
> cannot catch. `is_own_membership` in `respond_to_work_order_schedule` is what actually stops one
> person answering for another, and it never depended on the role.

### `backend/app/api/v1/routers/security_operations.py`

**Layers** — service `security_service` · repository `security_repository` ·
schemas `domain/security_schemas.py`, `domain/vocabularies.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/security/exports/{dataset}` | `export_dataset` :671 | `export_dataset_api_v1_security_exports__dataset__get` | 200 `text/csv` | § `GET …/exports/{dataset}` |
| `POST /api/v1/security/gate/verify` | `verify_credential` :547 | `verify_credential_api_v1_security_gate_verify_post` | 200 GateVerification | § `POST /api/v1/security/gate/verify` (API.md:7853) |
| `GET /api/v1/security/incidents` | `list_incidents` :458 | `list_incidents_api_v1_security_incidents_get` | 200 array of SecurityIncident | § `GET …/incidents` |
| `POST /api/v1/security/incidents` | `record_incident` :479 | `record_incident_api_v1_security_incidents_post` | 201 SecurityIncident | § `POST …/incidents` |
| `PATCH /api/v1/security/incidents/{incident_id}` | `update_incident` :516 | `update_incident_api_v1_security_incidents__incident_id__patch` | 200 SecurityIncident | § `PATCH …/incidents/{incidentId}` |
| `GET /api/v1/security/material-movements` | `list_movements` :295 | `list_movements_api_v1_security_material_movements_get` | 200 array of MaterialMovement | § `GET …/material-movements` |
| `POST /api/v1/security/material-movements` | `record_movement` :325 | `record_movement_api_v1_security_material_movements_post` | 201 MaterialMovement | § `POST …/material-movements` |
| `POST /api/v1/security/material-movements/{movement_id}/return` | `return_movement` :352 | `return_movement_api_v1_security_material_movements__movement_id__return_post` | 200 MaterialMovement | § `POST …/{movementId}/return` |
| `GET /api/v1/security/offline-bundle` | `offline_bundle` :588 | `offline_bundle_api_v1_security_offline_bundle_get` | 200 OfflineBundle | § `GET …/offline-bundle` |
| `POST /api/v1/security/offline-reconcile` | `offline_reconcile` :629 | `offline_reconcile_api_v1_security_offline_reconcile_post` | 200 OfflineReconcileResult | § `POST …/offline-reconcile` |
| `GET /api/v1/security/posts` | `list_posts` :99 | `list_posts_api_v1_security_posts_get` | 200 array of SecurityPost | § `GET /api/v1/security/posts` (API.md:7527) |
| `POST /api/v1/security/posts` | `create_post` :114 | `create_post_api_v1_security_posts_post` | 201 SecurityPost | § `POST /api/v1/security/posts` (API.md:7546) |
| `PATCH /api/v1/security/posts/{post_id}` | `update_post` :136 | `update_post_api_v1_security_posts__post_id__patch` | 200 SecurityPost | § `PATCH …/posts/{postId}` |
| `GET /api/v1/security/roster` | `list_roster` :262 | `list_roster_api_v1_security_roster_get` | 200 array of RosterEntry | § `GET /api/v1/security/roster` (API.md:7648) |
| `GET /api/v1/security/shifts` | `list_shifts` :166 | `list_shifts_api_v1_security_shifts_get` | 200 array of SecurityShift | § `GET /api/v1/security/shifts` (API.md:7575) |
| `POST /api/v1/security/shifts` | `create_shift` :204 | `create_shift_api_v1_security_shifts_post` | 201 SecurityShift | § `POST /api/v1/security/shifts` (API.md:7602) |
| `PATCH /api/v1/security/shifts/{shift_id}` | `update_shift` :233 | `update_shift_api_v1_security_shifts__shift_id__patch` | 200 SecurityShift | § `PATCH …/shifts/{shiftId}` |
| `GET /api/v1/security/water-tankers` | `list_tankers` :384 | `list_tankers_api_v1_security_water_tankers_get` | 200 array of WaterTankerLog | § `GET …/water-tankers` |
| `POST /api/v1/security/water-tankers` | `record_tanker` :402 | `record_tanker_api_v1_security_water_tankers_post` | 201 WaterTankerLog | § `POST …/water-tankers` |
| `PATCH /api/v1/security/water-tankers/{log_id}` | `update_tanker` :430 | `update_tanker_api_v1_security_water_tankers__log_id__patch` | 200 WaterTankerLog | § `PATCH …/water-tankers/{logId}` |

> **The export is the only operation in this repository whose success body is not JSON**, and it is
> declared rather than inferred: FastAPI cannot derive a schema from a bare `Response`, so the route
> carries an explicit `responses={200: {"content": {"text/csv": …}}}`. Without it the spec would
> advertise the operation with no success content at all, which is worse than describing it as a
> string — a client generator would produce a method that returns nothing.

> **This is the only router in the service-operations aggregate with a role guard**, and the note is
> here because the pattern above it is the opposite. `/worker/*` is authenticated-only by design; a
> gate belongs to one society, so this one resolves a community from the caller's membership. The
> dependency is local to the router (`require_gate_membership`) rather than
> `require_membership_role`, because the latter reads the role off the caller's **default**
> membership and a guard who lives in one community and works another's barrier would be refused
> their own register. See `API.md` §19.

> Three operations share an API.md subsection with their sibling read rather than getting one each —
> the two `PATCH`es and the material `return` — which is the §5.3 exception for a CRUD triple on one
> resource. Each is still named by its full path in the prose, because that is what `api_map_scan`
> matches on; the leave trio in `worker_schedule.py` cost a finding by saying *"the `DELETE`"*.

### `backend/app/api/v1/routers/skills.py`

**Layers** — service `skills_service` · repository `skills_repository` ·
schemas `domain/skill_schemas.py`, `domain/department_schemas.py`,
`domain/service_provider_schemas.py`, `domain/common_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/complaint-categories` | `list_categories` :79 | `list_categories_api_v1_complaint_categories_get` | 200 array of ComplaintCategory | § `GET /api/v1/complaint-categories` (API.md:4624) |
| `GET /api/v1/departments/{department_id}/skills` | `list_department_skills` :102 | `list_department_skills_api_v1_departments__department_id__skills_get` | 200 array of Skill | § `GET /api/v1/departments/{departmentId}/skills` (API.md:4654) |
| `POST /api/v1/departments/{department_id}/skills` | `add_department_skill` :145 | `add_department_skill_api_v1_departments__department_id__skills_post` | 201 SkillCreated | § `POST /api/v1/departments/{departmentId}/skills` (API.md:4699) |
| `PUT /api/v1/departments/{department_id}/skills` | `set_department_skills` :121 | `set_department_skills_api_v1_departments__department_id__skills_put` | 200 array of Skill | § `PUT /api/v1/departments/{departmentId}/skills` (API.md:4673) |
| `DELETE /api/v1/departments/{department_id}/skills/{skill_id}` | `remove_department_skill` :176 | `remove_department_skill_api_v1_departments__department_id__skills__skill_id__delete` | 200 MessageResult | § `DELETE /api/v1/departments/{departmentId}/skills/{skillId}` (API.md:4724) |
| `POST /api/v1/skills` | `create_skill` :47 | `create_skill_api_v1_skills_post` | 201 SkillCreated | § `GET /api/v1/skills` (API.md:4558) |

> **The skill surface is split across two routers on purpose, and this is the half with a guard.**
> `GET /api/v1/skills` is in `service_providers.py` above, because it exists for the service
> person's registration grid and any signed-in person may call it. Everything here is
> admin-or-manager. Splitting them keeps a read every worker makes separate from a write that
> changes a catalogue every community shares.

> **Two operations answer 200 or 201 from the same handler**, which no other row in this document
> does: `POST /skills` and `POST /departments/{id}/skills` create a trade or return the one that
> already answers to that name, and the status code carries which. The spec declares 201 as the
> documented success; the 200 is described in the API.md prose rather than the schema, because the
> body is identical and only `created` differs.

> `GET /api/v1/complaint-categories` was retired by the frontend wiring audit and reinstated by
> `skills_and_categories`. It is listed in `test_openapi_spec.py::test_retired_endpoints_stay_retired`'s comment
> block rather than its parameter list, which is where a reinstatement is recorded — see
> `docs/FRONTEND_WIRING_AUDIT.md` for the two premises that expired.

### `backend/app/api/v1/routers/complaint_routing.py`

**Layers** — service `complaint_routing_service` · repository `complaint_routing_repository` ·
schemas `domain/complaint_routing_schemas.py`, `domain/common_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `PATCH /api/v1/complaints/{complaint_id}/department` | `assign_department` :131 | `assign_department_api_v1_complaints__complaint_id__department_patch` | 200 MessageResult | **missing** |
| `POST /api/v1/complaints/{complaint_id}/department-requests` | `request_department_change` :169 | `request_department_change_api_v1_complaints__complaint_id__department_requests_post` | 201 MessageResult | **missing** |
| `PATCH /api/v1/complaints/{complaint_id}/department-requests/{request_id}` | `decide_department_change` :203 | `decide_department_change_api_v1_complaints__complaint_id__department_requests__request_id__patch` | 200 MessageResult | **missing** |
| `GET /api/v1/department-options` | `department_options` :104 | `department_options_api_v1_department_options_get` | 200 array of DepartmentOption | **missing** |
| `GET /api/v1/departments/{department_id}/complaint-department-requests` | `department_change_requests` :262 | `department_change_requests_api_v1_departments__department_id__complaint_department_requests_get` | 200 array of DepartmentChangeRequest | **missing** |
| `GET /api/v1/departments/{department_id}/complaints` | `department_complaints` :235 | `department_complaints_api_v1_departments__department_id__complaints_get` | 200 array of DepartmentComplaint | **missing** |
| `GET /api/v1/unassigned-complaints` | `unassigned_complaints` :67 | `unassigned_complaints_api_v1_unassigned_complaints_get` | 200 array of UnassignedComplaint | **missing** |

> **A router of its own rather than routes bolted onto `complaints.py`.** Its callers are the
> department populations — managers and supervisors — and its guard has to admit them.
> `complaints.py` is `require_admin` on the write it already has, so widening that router to admit a
> worker would quietly widen the complaint edit as well.

> **Two paths deliberately avoid the `/complaints/` and `/departments/` prefixes**, and the reason is
> a real collision rather than taste. `GET /complaints/unassigned` was swallowed by
> `resident_complaints.py`'s `GET /complaints/{complaintId}`, which read `unassigned` as a complaint
> id and ran the resident's read against it. Declaring the literal earlier would have worked and
> would have made the triage queue's correctness depend on the order two files are included in
> `app/api/v1/__init__.py`. `/unassigned-complaints` and `/department-options` are siblings, so
> nothing added later can capture them.

### `backend/app/api/v1/routers/supervisor_triage.py`

**Layers** — service `supervisor_triage_service` · repository `supervisor_triage_repository` ·
schemas `domain/supervisor_triage_schemas.py`, `domain/common_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/complaints/{complaint_id}/chat` | `open_complaint_chat` :256 | `open_complaint_chat_api_v1_complaints__complaint_id__chat_post` | 200 ComplaintThreadOpened | § `POST /api/v1/complaints/{complaintId}/chat` (API.md:7407) |
| `POST /api/v1/complaints/{complaint_id}/notes` | `add_complaint_note` :223 | `add_complaint_note_api_v1_complaints__complaint_id__notes_post` | 201 MessageResult | § `POST /api/v1/complaints/{complaintId}/notes` (API.md:7386) |
| `POST /api/v1/complaints/{complaint_id}/priority-raise` | `raise_complaint_priority` :183 | `raise_complaint_priority_api_v1_complaints__complaint_id__priority_raise_post` | 200 MessageResult | § `POST /api/v1/complaints/{complaintId}/priority-raise` (API.md:7356) |
| `POST /api/v1/complaints/{complaint_id}/resolve` | `resolve_complaint` :145 | `resolve_complaint_api_v1_complaints__complaint_id__resolve_post` | 200 MessageResult | § `POST /api/v1/complaints/{complaintId}/resolve` (API.md:7328) |
| `POST /api/v1/complaints/{complaint_id}/take-up` | `take_up_complaint` :102 | `take_up_complaint_api_v1_complaints__complaint_id__take_up_post` | 200 MessageResult | § `POST /api/v1/complaints/{complaintId}/take-up` (API.md:7263) |
| `GET /api/v1/departments/{department_id}/triage-snapshot` | `triage_snapshot` :60 | `triage_snapshot_api_v1_departments__department_id__triage_snapshot_get` | 200 TriageSnapshot | § `GET /api/v1/departments/{departmentId}/triage-snapshot` (API.md:7208) |

> **A router of its own rather than routes bolted onto a neighbour.** They straddle both: the
> snapshot answers with complaints *and* work orders, and take-up, resolve, priority, notes and chat
> are complaint verbs whose whole point is that they are **not** a dispatch. Filed under
> `complaint-routing` they would be described as being about which department owns a complaint; under
> `work-orders`, as turning one into a scheduled visit. They are neither. Nor are they `complaints.py`,
> which is the **admin's** community-wide surface behind `require_admin`; these are one department's,
> behind `can_supervise_department`, and a supervisor is not an admin.

> **Bucketing is the database's and the client never re-derives it.** *Live* (not `completed`,
> `cancelled` or `failed`) and — since amendment 2 — *committed* (an `accepted` assignment, or status
> `scheduled`) are written once, in `supervisor_triage_snapshot` (`20260822170000` §8). The service
> maps rows to DTOs and translates the vocabulary through `app/domain/vocabularies.py`; it filters
> nothing. A filter added here would be a sixth definition of *committed* in a place nobody would look
> for one.

> **Three of these five declare no request body, and that is load-bearing.** The frontend's house
> `post()` helper always sends `{}`, even for a body-less endpoint (`workerApi.acceptJob` is the
> precedent), so a required model would answer `422` to every press of the button — and an optional
> one would be a place to name somebody other than the caller, which the RPC would ignore anyway.
> Only `…/notes` takes a body, because a note has content.

> **The one action that *is* a dispatch is not here.** Force-assigning a named worker (2026-08-22
> ruling A4) is `force: true` on `POST /work-orders/{id}/assign`, in `work_orders.py` — it writes a
> work-order assignment, so it belongs beside the offer it overrides.

### `backend/app/api/v1/routers/telemetry.py`

**Layers** — repository `service_signup_telemetry_repository` · schemas `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/telemetry/service-signup` | `record_service_signup_event` :16 | `record_service_signup_event_api_v1_telemetry_service_signup_post` | 200 MessageResponse | § `POST /api/v1/telemetry/service-signup` (API.md:5145) |

> **The narrowest router here, deliberately.** One write, five permitted event names, and a random
> visitor id — no generic analytics surface and no experiment framework. Rows are deduplicated per
> event and deleted after thirty days by
> `20260811163408_service_signup_funnel_telemetry.sql`.

### `backend/app/api/v1/routers/settings.py`

**Layers** — service `settings_service` · repositories `settings_repository`, `tenancy_repository` ·
schemas `domain/settings_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/settings` | `get_settings` :56 | `get_settings_api_v1_settings_get` | 200 SettingsSnapshot | § `GET /api/v1/settings` (API.md:2770) |
| `PUT /api/v1/settings` | `update_settings` :75 | `update_settings_api_v1_settings_put` | 200 SettingsSnapshot | § `PUT /api/v1/settings` (API.md:2859) |

---

## 4. Backend files that shape the spec without serving a route

Changing any of these changes `openapi.yaml` even though no endpoint moved. They are the files to
check when the spec diff is larger than the route diff.

| File | Effect on the spec |
|---|---|
| [`backend/scripts/export_openapi.py`](../backend/scripts/export_openapi.py) | The generator. Injects `servers`, `info`, `license`; applies the annotations; runs `_check_coverage` (fails the build if the annotation table and the live routes disagree) and `_check_request_bodies` (fails if `GET`/`HEAD`/`DELETE` declares a body) |
| [`backend/scripts/api_annotations.py`](../backend/scripts/api_annotations.py) | Per-operation error responses, `x-user-stories`, and descriptions for handlers with no docstring. Error statuses are **unioned** with what the app declares, never subtracted — so this table can over-claim a status silently |
| [`backend/app/main.py`](../backend/app/main.py) | Mounts the router at `/api/v1` with an app-wide `422: ErrorResponse`, so every operation documents 422 |
| [`backend/app/core/exceptions.py`](../backend/app/core/exceptions.py) | The exception→status map (401/403/404/409/422/503/400) and the single `{"error": {...}}` envelope every handler emits |
| [`backend/app/core/pg_errors.py`](../backend/app/core/pg_errors.py) | Maps SQLSTATE (`HB409`, `HBUSE`, `23505`) onto `ConflictError`. A 409 can be reachable through here without any `raise ConflictError` in the service |
| [`backend/app/api/deps.py`](../backend/app/api/deps.py), [`admin_deps.py`](../backend/app/api/admin_deps.py) | The auth dependencies. Their presence is what produces `security` on an operation |
| `backend/app/domain/*.py` | Every Pydantic model here becomes a `components.schemas` entry — **230** of them today (~~131~~ on 2026-08-11; the count is `len(spec['components']['schemas'])`, so it includes the generated `Page_…` wrappers) |
| [`backend/tests/test_openapi_spec.py`](../backend/tests/test_openapi_spec.py) | Runs `--check` inside the suite, so a stale spec fails CI |

---

## 5. Known gaps, as of 2026-08-12

These are the reasons this file exists. Everything below is **documented-but-imprecise**, not
missing: all **199** operations are in the spec, with correct paths, methods, request bodies and
status codes. What is wrong is the *body* description on eleven of them, and the *prose coverage* on
nine. *(Read 179 until 2026-08-12 and 195 until 2026-08-20; the surface has moved three times while
the twenty findings did not.)*

**Every one of the twenty is inherited, and none is on a surface this branch built.** That is not a
boast — it is the reason the count has not moved in three months of adding endpoints, and the
reason a *new* finding is worth stopping for.

### 5.1 Success bodies the spec does not describe

| Operation | What the spec says | What the code returns | Verdict |
|---|---|---|---|
| `GET /api/v1/auth/methods` | 200 `{}`, statuses `200 422 500` | `{"primary": "google", "methods": [{"id","kind","label","enabled"}]}`, an `ETag`, and a **304** to a matching `If-None-Match` | **Defect.** The response models `AuthMethodsResponse` and `AuthMethod` are absent from `components.schemas` entirely, and 304 is undocumented. The handler returns a raw `Response`/`JSONResponse` with no `response_model`, so FastAPI has nothing to emit. The sign-in screen calls this before rendering |
| `POST /admin/access-requests/{id}/approve` · `/reject` · `/blacklist` | 200 free-form object | Raw Postgres RPC output | Under-documented. `-> dict` annotations |
| `POST /dashboard/amenities`, `PUT` and `DELETE /dashboard/amenities/{id}` | 200 free-form object | The raw DB row; `DELETE` returns `{"id": …}` | Under-documented, and the row **differs by deployment** — `dashboard_repository` builds a different shape when `schema_generation() == "legacy"`. There is no single true schema to document until that branch is resolved |
| The four OAuth `307`s | 307, no `Location` header documented | `RedirectResponse` | Minor. The body is genuinely empty; only the header is missing |

### 5.2 Operations with no API.md coverage

Nine operations have no reference section. API.md's header states that every `###` heading
corresponds to a real operation — which is true and is checked — but the reverse has never been
checked, and this is what it hides.

| Family | Operations | Where they appear today |
|---|---|---|
| Access requests — `GET /access-requests/mine`, `POST /access-requests/{id}/withdraw`, and the admin `approve` · `reject` · `blacklist` | 5 | One prose sentence in [API.md § 6. People](API.md#6-people) and one traceability row at §16.6 |
| `GET /communities/admin/units`, `GET /communities/search` | 2 | §16.6 row only |
| `PUT` and `DELETE /dashboard/amenities/{id}` | 2 | Nowhere; `POST` gets a §16.6 row |

> **`GET /communities/search` is here because the scan was wrong about it, and the regenerated table
> is what said so.** `api_map_scan.py` tested whether a path appeared *anywhere* in `API.md` as a
> substring, and §18 documents `GET /worker/communities/search` — a different endpoint that happens
> to end the same way. So a genuinely undocumented operation reported clean, while its row in §3 had
> said `**missing**` all along. The row was right. The scan now anchors the match on a left boundary
> (a longer path is not a mention of a shorter one) and **the operation-side baseline moves 19 → 20**
> — not a regression, a defect that had been hiding behind a bad test.
>
> *(This section read **nine, plus two named only in passing prose** until 2026-08-11. Two of those
> eleven have since genuinely gained coverage — `POST /access-requests` and
> `GET /admin/access-requests` — so the access-request row names its five remaining operations
> individually rather than saying "all 7", which is what let the drift hide.)*

### 5.3 Deliberately not documented further — do not "fix" these

- **The two SSE endpoints** (`GET /events`, `GET /dashboard/events`) declare `text/event-stream` with
  no schema on purpose.
- **The 14 "over-claimed" error statuses** a static call-graph walk reports (mostly 404 and 409 on
  auth and visitor-pass routes) are reachable in reality — through `pg_errors.py` SQLSTATE mapping,
  which no static walker crosses.
- **The 3 "undocumented" error statuses** it reports are false too: `logout`'s 503 is swallowed by an
  `except`, and the two 404s are defensive read-back paths, one of them marked
  `# pragma: no cover - the RPC just created it`.

---

## 6. Standing rule: this file, `openapi.yaml` and `API.md` move together

**Any commit that adds, removes or changes a backend endpoint updates all four artifacts in that same
commit** — the code, the regenerated spec, the API.md section, and the row in this file. An endpoint
that exists only in Python is invisible to the frontend and to the testing team.

### 6.1 When you write backend code

1. Give the handler a `response_model`, or a return annotation the generator can resolve. **Never
   leave a success body undescribed** — a bare `Response`, `JSONResponse` or `-> dict` produces `{}`
   in the spec and an untyped blob in every generated client. If a raw response is unavoidable
   (redirects, streams), declare the extra responses explicitly in the decorator.
2. Declare every non-default status the handler can return, including `304` and `307`.
3. Regenerate and add the reference section:

   ```bash
   cd backend && python scripts/export_openapi.py
   ```

4. Regenerate the tables here — **do not hand-write the row**:

   ```bash
   cd backend && python scripts/regen_mapper.py
   ```

   [`regen_mapper.py`](../backend/scripts/regen_mapper.py) rewrites every §3 table from the live app
   and the spec: route, `handler :line`, `operationId`, success schema. It **preserves** the one
   column it cannot derive — which `API.md` section covers the operation — keeping your wording and
   refreshing only the line number, and it preserves the `**bold**` that marks a §5 defect. Prose,
   layer chains and notes are untouched. A new operation arrives with its `API.md` cell filled in if
   a `###` heading matches it and `**missing**` if not, which is your cue to write the section.
5. Give the operation its `x-user-stories` entry in
   [`api_annotations.py`](../backend/scripts/api_annotations.py) — the exporter refuses to build
   without one. **If that changes a story's verdict, change it in all three places**: that file,
   [`API.md` §16](API.md#16-user-stories--endpoints), and the `Backend:` line in
   [`product/USER_STORIES.md`](product/USER_STORIES.md). The exporter guards operation → story; it
   has never guarded story → verdict, which is how six of those lines went stale for four days.

### 6.2 After every pull from the repository

Others' endpoints arrive without our documentation, and the pull is the only moment anyone reliably
looks. Two commands, in this order:

```bash
cd backend && python scripts/export_openapi.py --check
```

If that reports the spec is stale, somebody changed a handler without regenerating — regenerate and
commit it. If it passes, the spec matches what FastAPI *declares*; it does **not** prove the
declaration matches what the handler *does*, which is the gap every finding in §5 lives in. So then:

```bash
cd backend && python scripts/api_map_scan.py && python scripts/regen_mapper.py --check
```

`--check` on the regenerator is the cheap half: it exits 1 the moment a handler has moved, a
response model has changed, or an `API.md` heading has shifted a line — none of which any other
check sees, and all of which somebody else's commit can cause. Run it, then run the regenerator
proper.

[`api_map_scan.py`](../backend/scripts/api_map_scan.py) asks the five questions this file exists to
answer — is every live operation in the spec and vice versa, does each one describe its success body
with a named component, does `API.md` document it, is it listed here, and **do the three records of
each user story's verdict agree** — and prints one line per finding with the source file and line.
`--strict` exits non-zero, for a hook or CI.

That fifth question reports `STORY VERDICT` when `USER_STORIES.md`, `API.md` §16 and
`api_annotations.py` disagree about a story, and `STORY UNBACKED` when a story credited as served or
partial has no operation declaring it. Both were real on 2026-08-08 — six of the first and one of the
second — and neither was visible to any check that existed.

**A finding is not automatically a defect.** As of 2026-08-11 the scan reports **20**: the eleven
untyped bodies and nine undocumented operations in §5, every one of which already carries a
verdict. All 24 stories agree across all three records. *(Re-verified 2026-08-12 against a surface
that had since grown to 195 operations: still exactly those 20, still all 24 stories agreeing —
Sessions 67–68 added twenty operations and retired four without adding a finding, which is the
claim §5's opening paragraph makes and the only evidence that would falsify it.)* *(19 until the same day, when the
substring bug in §5.2's note was fixed and `GET /communities/search` stopped hiding.)*
*(Re-verified again 2026-08-20 against **199** operations: still exactly those 20, still all 24
stories agreeing. `POST /complaints/admin-raise` arrived with a named response component, an
`API.md` section and its two story tags, so it added none of the three kinds of finding.)*
That is the point of §5 — anything the scan reports that is *not* recorded there is new, and needs a
verdict written in the same pass. An undocumented endpoint nobody wrote down is indistinguishable
next month from one deliberately left free-form.

### 6.3 Verification commands used to build this file

```bash
cd backend && python scripts/export_openapi.py --check && python scripts/api_map_scan.py && python -m pytest -q
```

**And the recount behind [`API.md` §16.6](API.md#166-endpoints-that-serve-no-story-and-why-that-is-fine).**
That section's headline number and its whole table are the story-mapping totals, and until
2026-08-11 they were counted by hand — which is how they came to say 90 of 163 when the spec said
106 of 179. Nothing enforces them, because a coverage total is a summary rather than a contract, so
this is the command that keeps them honest:

```bash
cd backend && python -c "import yaml,collections; s=yaml.safe_load(open('../docs/openapi.yaml',encoding='utf-8')); ops=[o for p in s['paths'].values() for m,o in p.items() if m in ('get','post','put','patch','delete')]; m=[o for o in ops if o.get('x-user-stories')]; print(len(m),'mapped /',len(ops)-len(m),'unmapped /',len(ops),'total'); print(collections.Counter(o['x-no-user-story']['api-type'] for o in ops if not o.get('x-user-stories')))"
```

The same grouping the table's rows use is `x-no-user-story.rationale` — one distinct rationale per
row, so a group that splits or merges in
[`api_annotations.py`](../backend/scripts/api_annotations.py) shows up as a row that no longer
matches rather than as a number that quietly stops adding up.

---

## 7. Change log for this file

| Date | Change |
|---|---|
| 2026-08-20 | **One operation added and six guards changed without a single byte of spec moving.** `POST /complaints/admin-raise` arrives with a named response component (`AdminComplaintRaised`), an `API.md` section and two story tags, so the findings stay at **20** and the stories at 24-agreeing; the surface is **199 operations across 168 paths**. Three of the four operations added since the 2026-08-12 recount were **not** this session's — the spec at `ed9a131` already held 198 across 167 while `API.md`'s banner still said 195 across 164, which is the fourth appearance of the drift the row below describes. Regenerated: **126 rows changed plus the one new row**, and every one of the 126 is an `API.md:NNNN` reference moved by this session's edits to §1.2, §7 and §16.4, or a handler line number in `complaints.py`, `resident_complaints.py` or `resident_scheduling.py`. *(The regenerator's own tally said "815 row(s) differ"; it zips old against new line-for-line, so a single inserted row makes every line below it compare unequal. The count in that message is not the number of real changes — read the diff, not the tally.)* **The guard change is the invisible half and is recorded only in prose**: `require_resident_capability` replaced `require_membership_role("resident")` on four resident-complaint routes and both resident-scheduling routes, and replaced *active membership alone* on `POST /complaints` — five widenings and one narrowing, none of which moves a path, a body or a status code, so `export_openapi.py --check` is byte-identical on all seven. Same class as the `0041` row of 2026-08-10 |
| 2026-08-12 | **The same failure mode as the 2026-08-11 row, one session later and caught by the cheap half.** Session 68's close-out edited `API.md` *after* the last `regen_mapper.py` run, so **94 rows** carried `API.md:NNNN` references off by up to 59 lines while every route, `operationId` and schema in them was correct — `--check` exits 1 on exactly this and nothing else does. Regenerated. **Three prose numbers around the tables were stale in the same way the tables were not**: §4 said 131 `components.schemas` (**230**), §5 said all 179 operations (**195**), and §5.2 pinned the access-request prose to `API.md:746`, a line reference now replaced by an anchor so it cannot drift again. The twenty findings and the 24 story verdicts were **re-verified unchanged** against the larger surface, which is the claim §5's opening paragraph makes and the only thing that would have falsified it. `API.md`'s own banner (179→**195 across 164 paths**) and §16.6 (106-of-179 → **122-of-195**, table rebuilt to the spec's 28 `x-no-user-story` groups — four of which it had no row for at all) went with it |
| 2026-08-11 | **§3 is generated now.** `scripts/regen_mapper.py` rewrites all 179 rows from the live app and the spec, on the PO's instruction to *"regenerate the mapping … to match the current api state"*. The prompt was the previous row's finding: the `API.md:NNNN` references had drifted by roughly seventy lines, because `API.md` grows above a heading and every reference below it moves — invisible to every check, and not worth fixing by hand because it would be wrong again on the next edit. **166 of the 179 rows changed**, all of them line numbers and handler positions; not one route, `operationId` or schema was wrong, which is why nothing had caught it. The script preserves what it cannot derive: the *choice* of which `API.md` section covers an operation, and the `**bold**` that marks a §5 defect. **Two things fell out of doing it mechanically.** Some rows quoted the route in camelCase against §1's own rule, now normalised to how the code declares it. And `GET /communities/search` had been marked `**missing**` in §3 while the scan reported it documented — the row was right: `api_map_scan.py` matched paths as bare substrings, so §18's `GET /worker/communities/search` was answering for it. Fixed with a left-boundary anchor; **the operation-side baseline moves 19 → 20**, which is a defect surfacing, not a regression |
| 2026-08-11 | **The tables were current and every number *around* them was stale**, which is the failure mode this file was built to catch happening to this file. Sixteen operations arrived across `0043`–`0047` (ten departures, five messages, one roster read) and each got its row; the header still said 99 operations and 686 tests, §5 still said "as of `98d557a`", §6.2 still said 20 findings, and §5.2 still claimed eleven undocumented operations when three had since gained coverage. All corrected against the branch: **179 operations across 150 paths**, 843 tests, findings **19** (eleven untyped bodies, eight undocumented). `API.md` §16 had the same disease and worse — its coverage table read 8/9/7 when the per-story verdicts it summarises said 15/6/3, and §16.6 read 90-of-163 against a spec saying 106-of-179. §6.3 gains the command that recounts both, and §16.6's table was rebuilt so its rows *are* the spec's `x-no-user-story` groups |
| 2026-08-10 | **`StaffMember` gained `serviceProviderId` (`0042`), which is a response-shape change `--check` *does* see** — unlike the guard changes in the row below. Regenerated; surface unchanged at **163 operations across 138 paths**, 824 tests, operation-side findings still **19**. Two prose corrections in `API.md` that no tool can catch: §8's `rank` vocabulary still printed `head`, which `0035` replaced five migrations ago, and two endpoints stated that an invited or rejected provider *cannot* be notified — true when written, false since `0041` |
| 2026-08-10 | **`0041` re-addressed the notification substrate from a membership to a person, and five operations changed their guard without changing their shape.** `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`, `GET /push/vapid-key`, `POST /push/subscriptions` and `POST /push/subscriptions/unregister` moved from `get_active_membership` to `get_current_user`. **Not one path, method, request body or response model moved**, so `export_openapi.py --check` is byte-identical and this is precisely the class of change §6.2 step 1 cannot see — the same class as `7d830e1` below. The prose in `API.md` §5.2 and §5.3 and the error tables were updated by hand. Surface unchanged at **163 operations across 138 paths**, 824 tests, operation-side findings still **19**. `US-2.4` moved to *served* in all three places the story gate compares, which is the check that caught the same move being half-done a day earlier |
| 2026-08-09 | Service personnel added — six operations under a new router table, from `0034`. Surface is now **105 operations across 91 paths**, 713 tests passing. Operation-side findings stay at **20**: all six are documented in `API.md` §18 and listed here, so the count neither rose nor fell. Worth noting for whoever scans next — this is the first router in §3 that declares no membership dependency, and that is deliberate rather than an omission to be tidied away; the note under its table says why |
| 2026-08-09 | Rescanned at `main` @ `1138f2e`, four commits ahead of where the last scan ran. Operation-side findings unchanged at 20, story findings zero, 694 tests passing. One real catch: `7d830e1` routed `POST /onboarding/community` through `pg_errors.translate` and widened its error surface to include 422 without moving a route or a response model — invisible to `--check`, and the case §6.2 step 1 cannot see. Declared in [`api_annotations.py`](../backend/scripts/api_annotations.py) and regenerated |
| 2026-08-08 | §6.1 gains step 5 and §6.2 a fifth question, after a user-story sweep found the verdict for six stories stale in [`product/USER_STORIES.md`](product/USER_STORIES.md) and one story (`US-3.1`) credited as partial by prose that no operation declared. The operation-side findings are unchanged at 20 |
| 2026-08-08 | Created at `main` @ `98d557a`, after a full backend↔spec audit prompted by a testing-team report that the yaml looked out of sync. It was not: the spec regenerates byte-identical and all 99 operations match in both directions. The real gaps are the eleven imprecise success bodies and nine undocumented operations in §5 |
