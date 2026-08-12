# API ↔ code ↔ spec mapper

**Verified against `main` @ `98d557a` on 2026-08-08.** 103 registered routes, of which **99 are API
operations** and 4 are FastAPI's own docs endpoints (`/docs`, `/docs/oauth2-redirect`, `/redoc`,
`/openapi.json`). All 99 appear in [`openapi.yaml`](openapi.yaml); the spec documents nothing that
the code does not serve. 686 tests pass.

This file answers one question in one place: **for a given backend source file, which endpoints does
it implement, and where does each one live in the spec and in the reference docs?** It is the third
leg of the documentation set —

| File | What it is | How it is maintained |
|---|---|---|
| [`openapi.yaml`](openapi.yaml) | The machine contract. Shapes, status codes, traceability | **Generated**, never hand-edited |
| [`API.md`](API.md) | The prose contract. Why a rule exists, what a guard protects | Hand-written |
| **`api_yaml_mapper.md`** (this file) | The index tying source files to both of the above | Hand-written; [`api_map_scan.py`](../backend/scripts/api_map_scan.py) says when it has fallen behind |

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
| `GET /health` | `health` :83 | `health_health_get` | 200 inline | § `GET /health` (API.md:310) |

### `backend/app/api/v1/routers/access_requests.py`

**Layers** — service `access_request_service` · repositories `access_requests_repository`,
`profiles_repository` · schemas `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/access-requests` | `create_access_request` :22 | `create_access_request_api_v1_access_requests_post` | 201 AccessRequestResponse | mention only — § 6. People (API.md:709) |
| `GET /api/v1/access-requests/mine` | `my_access_requests` :35 | `my_access_requests_api_v1_access_requests_mine_get` | 200 AccessRequestListResponse | **missing** |
| `POST /api/v1/access-requests/{request_id}/withdraw` | `withdraw_access_request` :42 | `withdraw_access_request_api_v1_access_requests__request_id__withdraw_post` | 200 AccessRequestResponse | **missing** |
| `GET /api/v1/admin/access-requests` | `admin_access_requests` :54 | `admin_access_requests_api_v1_admin_access_requests_get` | 200 AccessRequestListResponse | mention only — § 6. People (API.md:709) |
| `POST /api/v1/admin/access-requests/{request_id}/approve` | `approve_access_request` :63 | `approve_access_request_api_v1_admin_access_requests__request_id__approve_post` | 200 free-form object | **missing** |
| `POST /api/v1/admin/access-requests/{request_id}/blacklist` | `blacklist_access_request` :87 | `blacklist_access_request_api_v1_admin_access_requests__request_id__blacklist_post` | 200 free-form object | **missing** |
| `POST /api/v1/admin/access-requests/{request_id}/reject` | `reject_access_request` :75 | `reject_access_request_api_v1_admin_access_requests__request_id__reject_post` | 200 free-form object | **missing** |

### `backend/app/api/v1/routers/amenities.py`

**Layers** — service `amenities_service` · repositories `amenities_repository`, `tenancy_repository`
· schemas `domain/amenity_schemas.py`, `domain/common_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/amenities/{amenity_id}/approvals` | `list_approvals` :194 | `list_approvals_api_v1_amenities__amenity_id__approvals_get` | 200 Page_ApprovalRequest_ | § `GET /api/v1/amenities/{amenityId}/approvals` (API.md:1696) |
| `POST /api/v1/amenities/{amenity_id}/blocks` | `block_slot` :173 | `block_slot_api_v1_amenities__amenity_id__blocks_post` | 201 BookingSummary | § `POST /api/v1/amenities/{amenityId}/blocks` (API.md:1669) |
| `GET /api/v1/amenities/{amenity_id}/bookings` | `list_amenity_bookings` :66 | `list_amenity_bookings_api_v1_amenities__amenity_id__bookings_get` | 200 Page_BookingSummary_ | § `GET /api/v1/amenities/{amenityId}/bookings` (API.md:1516) |
| `POST /api/v1/amenities/{amenity_id}/bookings` | `create_admin_booking` :113 | `create_admin_booking_api_v1_amenities__amenity_id__bookings_post` | 201 BookingSummary | § `POST /api/v1/amenities/{amenityId}/bookings` (API.md:1592) |
| `POST /api/v1/amenities/{amenity_id}/bookings/request` | `request_booking` :141 | `request_booking_api_v1_amenities__amenity_id__bookings_request_post` | 201 Page_BookingSummary_ | § `POST /api/v1/amenities/{amenityId}/bookings/request` (API.md:1631) |
| `GET /api/v1/amenities/{amenity_id}/ledger` | `list_ledger` :334 | `list_ledger_api_v1_amenities__amenity_id__ledger_get` | 200 Page_LedgerTransaction_ | § `GET /api/v1/amenities/{amenityId}/ledger` (API.md:1820) |
| `GET /api/v1/amenities/{amenity_id}/ledger/summary` | `get_ledger_summary` :378 | `get_ledger_summary_api_v1_amenities__amenity_id__ledger_summary_get` | 200 LedgerSummary | § `GET /api/v1/amenities/{amenityId}/ledger/summary` (API.md:1909) |
| `POST /api/v1/amenity-bookings/cancel` | `cancel_bookings` :277 | `cancel_bookings_api_v1_amenity_bookings_cancel_post` | 200 MessageResult | § `POST /api/v1/amenity-bookings/cancel` (API.md:1766) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/charges` | `add_charge` :474 | `add_charge_api_v1_amenity_bookings__occurrence_id__charges_post` | 201 LedgerTransaction | § `POST /api/v1/amenity-bookings/{occurrenceId}/charges` (API.md:2010) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/damage` | `deduct_damage` :449 | `deduct_damage_api_v1_amenity_bookings__occurrence_id__damage_post` | 201 LedgerTransaction | § `POST /api/v1/amenity-bookings/{occurrenceId}/damage` (API.md:1989) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/force-cancel` | `force_cancel_booking` :305 | `force_cancel_booking_api_v1_amenity_bookings__occurrence_id__force_cancel_post` | 200 BookingSummary | § `POST /api/v1/amenity-bookings/{occurrenceId}/force-cancel` (API.md:1800) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/payments` | `record_payment` :400 | `record_payment_api_v1_amenity_bookings__occurrence_id__payments_post` | 201 LedgerTransaction | § `POST /api/v1/amenity-bookings/{occurrenceId}/payments` (API.md:1935) |
| `POST /api/v1/amenity-bookings/{occurrence_id}/refund` | `refund_deposit` :424 | `refund_deposit_api_v1_amenity_bookings__occurrence_id__refund_post` | 201 LedgerTransaction | § `POST /api/v1/amenity-bookings/{occurrenceId}/refund` (API.md:1965) |
| `POST /api/v1/amenity-bookings/{series_id}/approve` | `approve_booking` :234 | `approve_booking_api_v1_amenity_bookings__series_id__approve_post` | 200 Page_BookingSummary_ | § `POST /api/v1/amenity-bookings/{seriesId}/approve` (API.md:1730) |
| `POST /api/v1/amenity-bookings/{series_id}/reject` | `reject_booking` :254 | `reject_booking_api_v1_amenity_bookings__series_id__reject_post` | 200 Page_BookingSummary_ | § `POST /api/v1/amenity-bookings/{seriesId}/reject` (API.md:1745) |
| `GET /api/v1/amenity-reports` | `get_report` :503 | `get_report_api_v1_amenity_reports_get` | 200 AmenityReport | § `GET /api/v1/amenity-reports` (API.md:2030) |

> `POST …/bookings/request`, `…/approve` and `…/reject` returning `Page[BookingSummary]` is
> deliberate, not a mis-declared model: one request covers several days and the handler returns every
> day it touched. The docstrings say so.

### `backend/app/api/v1/routers/auth.py`

**Layers** — service `auth_service` · repository `profiles_repository` · schemas `domain/schemas.py`

Owned by the auth workstream. The spec's error codes and descriptions for these operations come from
[`api_annotations.py`](../backend/scripts/api_annotations.py), not from the handlers.

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/auth/csrf` | `csrf` :101 | `csrf_api_v1_auth_csrf_get` | 200 MessageResponse | mention only — § 3.1 (API.md:336) |
| `POST /api/v1/auth/email/resend` | `resend_email` :170 | `resend_email_api_v1_auth_email_resend_post` | 200 MessageResponse | mention only — § 3.3 Email and password |
| `POST /api/v1/auth/email/verify` | `verify_email` :161 | `verify_email_api_v1_auth_email_verify_post` | 200 MessageResponse | mention only — § 3.3 Email and password (API.md:357) |
| `GET /api/v1/auth/google/callback` | `google_callback` :137 | `google_callback_api_v1_auth_google_callback_get` | 307 free-form object | mention only — § 3.2 Google OAuth (API.md:344) |
| `GET /api/v1/auth/google/start` | `google_start` :132 | `google_start_api_v1_auth_google_start_get` | 307 free-form object | mention only — § 3.2 Google OAuth (API.md:344) |
| `POST /api/v1/auth/logout` | `logout` :233 | `logout_api_v1_auth_logout_post` | 200 MessageResponse | mention only — § 3.5 Session lifecycle (API.md:401) |
| `GET /api/v1/auth/methods` | `auth_methods` :92 | `auth_methods_api_v1_auth_methods_get` | **200 free-form object** | mention only — § 3. Authentication (API.md:325) |
| `GET /api/v1/auth/oauth/{provider}/callback` | `oauth_callback` :117 | `oauth_callback_api_v1_auth_oauth__provider__callback_get` | 307 free-form object | mention only — § 3.2 Google OAuth (API.md:343) |
| `GET /api/v1/auth/oauth/{provider}/start` | `oauth_start` :107 | `oauth_start_api_v1_auth_oauth__provider__start_get` | 307 free-form object | mention only — § 3.2 Google OAuth (API.md:342) |
| `POST /api/v1/auth/password/reset/complete` | `password_reset_complete` :207 | `password_reset_complete_api_v1_auth_password_reset_complete_post` | 200 MessageResponse | mention only — § 3.4 Password recovery (API.md:391) |
| `POST /api/v1/auth/password/reset/request` | `password_reset_request` :191 | `password_reset_request_api_v1_auth_password_reset_request_post` | 200 MessageResponse | mention only — § 3.4 Password recovery |
| `POST /api/v1/auth/password/reset/verify` | `password_reset_verify` :200 | `password_reset_verify_api_v1_auth_password_reset_verify_post` | 200 MessageResponse | mention only — § 3.4 Password recovery (API.md:390) |
| `POST /api/v1/auth/password/sign-in` | `password_sign_in` :151 | `password_sign_in_api_v1_auth_password_sign_in_post` | 200 MessageResponse | mention only — § 3.3 Email and password |
| `POST /api/v1/auth/password/sign-up` | `password_sign_up` :142 | `password_sign_up_api_v1_auth_password_sign_up_post` | 200 MessageResponse | mention only — § 3.3 Email and password (API.md:355) |
| `POST /api/v1/auth/refresh` | `refresh` :223 | `refresh_api_v1_auth_refresh_post` | 200 MessageResponse | mention only — § 3.5 Session lifecycle (API.md:400) |
| `GET /api/v1/auth/session` | `session` :218 | `session_api_v1_auth_session_get` | 200 SessionContext | mention only — § 1.2 Authentication (API.md:116) |

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
| `PATCH /api/v1/complaints/{complaint_id}` | `update_complaint` :30 | `update_complaint_api_v1_complaints__complaint_id__patch` | 200 MessageResult | § `PATCH /api/v1/complaints/{complaintId}` (API.md:740) |
| `POST /api/v1/complaints/{complaint_id}/comments` | `add_comment` :56 | `add_comment_api_v1_complaints__complaint_id__comments_post` | 201 MessageResult | § `POST /api/v1/complaints/{complaintId}/comments` (API.md:772) |

### `backend/app/api/v1/routers/dashboard.py`

**Layers** — service `dashboard_service` · repository `dashboard_repository` · schemas
`domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/dashboard/amenities` | `create_amenity` :47 | `create_amenity_api_v1_dashboard_amenities_post` | **200 free-form object** | mention only — § 16.6 (API.md:3506) |
| `PUT /api/v1/dashboard/amenities/{amenity_id}` | `update_amenity` :60 | `update_amenity_api_v1_dashboard_amenities__amenity_id__put` | **200 free-form object** | **missing** |
| `DELETE /api/v1/dashboard/amenities/{amenity_id}` | `delete_amenity` :74 | `delete_amenity_api_v1_dashboard_amenities__amenity_id__delete` | **200 free-form object** | **missing** |
| `GET /api/v1/dashboard/events` | `dashboard_events` :25 | `dashboard_events_api_v1_dashboard_events_get` | 200 `text/event-stream` | mention only — § 5.1 (API.md:494) |
| `GET /api/v1/dashboard/snapshot` | `get_dashboard_snapshot` :17 | `get_dashboard_snapshot_api_v1_dashboard_snapshot_get` | 200 DashboardSnapshot | mention only — § 5 (API.md:480) |

### `backend/app/api/v1/routers/departments.py`

**Layers** — service `departments_service` · repositories `departments_repository`,
`tenancy_repository` · schemas `domain/department_schemas.py`, `domain/common_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/departments` | `list_departments` :41 | `list_departments_api_v1_departments_get` | 200 Page_DepartmentDetail_ | § `GET /api/v1/departments` (API.md:958) |
| `POST /api/v1/departments` | `create_department` :80 | `create_department_api_v1_departments_post` | 201 DepartmentDetail | § `POST /api/v1/departments` (API.md:1033) |
| `GET /api/v1/departments/{department_id}` | `get_department` :101 | `get_department_api_v1_departments__department_id__get` | 200 DepartmentDetail | § `GET /api/v1/departments/{departmentId}` (API.md:1077) |
| `PATCH /api/v1/departments/{department_id}` | `update_department` :115 | `update_department_api_v1_departments__department_id__patch` | 200 DepartmentDetail | § `PATCH /api/v1/departments/{departmentId}` (API.md:1086) |
| `DELETE /api/v1/departments/{department_id}` | `delete_department` :142 | `delete_department_api_v1_departments__department_id__delete` | 200 MessageResult | § `DELETE /api/v1/departments/{departmentId}` (API.md:1114) |
| `PUT /api/v1/departments/{department_id}/staff` | `replace_staff` :166 | `replace_staff_api_v1_departments__department_id__staff_put` | 200 StaffMember[] | § `PUT /api/v1/departments/{departmentId}/staff` (API.md:1133) |
| `POST /api/v1/departments/{department_id}/staff` | `add_staff_member` :192 | `add_staff_member_api_v1_departments__department_id__staff_post` | 201 StaffMember | § `POST /api/v1/departments/{departmentId}/staff` (API.md:1160) |
| `PATCH /api/v1/departments/{department_id}/staff/{staff_id}` | `update_staff_member` :214 | `update_staff_member_api_v1_departments__department_id__staff__staff_id__patch` | 200 StaffMember | § `PATCH …/staff/{staffId}` (API.md:1177) |
| `DELETE /api/v1/departments/{department_id}/staff/{staff_id}` | `remove_staff_member` :237 | `remove_staff_member_api_v1_departments__department_id__staff__staff_id__delete` | 200 MessageResult | § `DELETE …/staff/{staffId}` (API.md:1195) |

### `backend/app/api/v1/routers/events.py`

**Layers** — service `dashboard_service` · repository `dashboard_repository` · schemas
`domain/schemas.py` · also `core/realtime.py` (the in-process fan-out hub)

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/events` | `events` :78 | `events_api_v1_events_get` | 200 `text/event-stream` | § 5.1 Live updates — `GET /events` (API.md:489) |

> The `text/event-stream` content type with no schema is **correct and intentional** — a client
> generated from a JSON schema would try to decode a live stream. `SSE_RESPONSES` in this file carries
> the comment explaining it.

### `backend/app/api/v1/routers/invitations.py`

**Layers** — services `invitation_service`, `auth_service` · repositories `invitations_repository`,
`memberships_repository`, `profiles_repository` · schemas `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/admin/invitations` | `create_invitation` :20 | `create_invitation_api_v1_admin_invitations_post` | 200 InvitationCreated | § `POST /api/v1/admin/invitations` (API.md:417) |
| `POST /api/v1/invitations/prepare` | `prepare_invitation` :29 | `prepare_invitation_api_v1_invitations_prepare_post` | 200 MessageResponse | § `POST /api/v1/invitations/prepare` (API.md:456) |
| `POST /api/v1/invitations/redeem` | `redeem_invitation` :36 | `redeem_invitation_api_v1_invitations_redeem_post` | 200 MessageResponse | § `POST /api/v1/invitations/redeem` (API.md:466) |

### `backend/app/api/v1/routers/money.py`

**Layers** — service `money_service` · repositories `money_repository`, `tenancy_repository` ·
schemas `domain/money_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/invoices` | `create_invoice` :46 | `create_invoice_api_v1_invoices_post` | 201 InvoiceDetail | § `POST /api/v1/invoices` (API.md:1229) |
| `POST /api/v1/invoices/{invoice_id}/payments` | `record_payment` :70 | `record_payment_api_v1_invoices__invoice_id__payments_post` | 201 InvoiceDetail | § `POST /api/v1/invoices/{invoiceId}/payments` (API.md:1270) |
| `GET /api/v1/billing-settings` | `get_billing_settings` :98 | `get_billing_settings_api_v1_billing_settings_get` | 200 BillingSettings | § `GET /api/v1/billing-settings` (API.md:1311) |
| `PUT /api/v1/billing-settings` | `update_billing_settings` :115 | `update_billing_settings_api_v1_billing_settings_put` | 200 BillingSettings | § `PUT /api/v1/billing-settings` (API.md:1353) |

### `backend/app/api/v1/routers/notices.py`

**Layers** — service `notices_service` · repository `notices_repository` · schemas
`domain/notice_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/notices` | `create_notice` :26 | `create_notice_api_v1_notices_post` | 201 NoticeCreated | § 12.1 `POST /notices` (API.md:2327) |

### `backend/app/api/v1/routers/notifications.py`

**Layers** — service `notifications_service` · repository `notifications_repository` · schemas
`domain/notification_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/notifications` | `list_notifications` :27 | `list_notifications_api_v1_notifications_get` | 200 NotificationFeed | § `GET /api/v1/notifications` (API.md:590) |
| `POST /api/v1/notifications/{notification_id}/read` | `mark_notification_read` :66 | `mark_notification_read_api_v1_notifications__notification_id__read_post` | 200 NotificationReadResult | § `POST /api/v1/notifications/{notificationId}/read` (API.md:617) |
| `POST /api/v1/notifications/read-all` | `mark_all_notifications_read` :92 | `mark_all_notifications_read_api_v1_notifications_read_all_post` | 200 NotificationReadResult | § `POST /api/v1/notifications/read-all` (API.md:626) |

### `backend/app/api/v1/routers/onboarding.py`

**Layers** — services `onboarding_service`, `auth_service` · repository `profiles_repository` ·
schemas `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/onboarding/community` | `create_community` :12 | `create_community_api_v1_onboarding_community_post` | 200 CommunityOnboardingResponse | [`POST /onboarding/community`](API.md#post-apiv1onboardingcommunity) |

### `backend/app/api/v1/routers/people.py`

**Layers** — service `people_service` · repositories `people_repository`, `tenancy_repository` ·
schemas `domain/people_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `POST /api/v1/admins` | `promote_admin` :27 | `promote_admin_api_v1_admins_post` | 200 AdminSummary | § 12.2 `POST /admins` (API.md:2382) |

### `backend/app/api/v1/routers/push.py`

**Layers** — service `push_service` · repository `push_repository` · schemas
`domain/notification_schemas.py`, `domain/schemas.py` · also `core/push.py`, `core/push_config.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/push/vapid-key` | `vapid_key` :33 | `vapid_key_api_v1_push_vapid_key_get` | 200 VapidPublicKey | § 5.3 Web Push (API.md:638) |
| `POST /api/v1/push/subscriptions` | `subscribe` :56 | `subscribe_api_v1_push_subscriptions_post` | 200 PushSubscriptionResult | § 5.3 Web Push (API.md:638) |
| `POST /api/v1/push/subscriptions/unregister` | `unsubscribe` :83 | `unsubscribe_api_v1_push_subscriptions_unregister_post` | 200 PushSubscriptionResult | § 5.3 Web Push (API.md:638) |

> `unregister` is a POST to a sub-path rather than `DELETE /push/subscriptions` with a body, because
> RFC 9110 gives no semantics to a body on `DELETE`. `_check_request_bodies` in the exporter fails the
> build if anyone reintroduces one.

### `backend/app/api/v1/routers/resident_amenities.py`

**Layers** — service `resident_amenities_service` · repository `resident_amenities_repository` ·
schemas `domain/resident_amenity_schemas.py`, `domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/amenities/available` | `list_available_amenities` :30 | `list_available_amenities_api_v1_amenities_available_get` | 200 Page_BookableAmenity_ | § `GET /api/v1/amenities/available` (API.md:1444) |

### `backend/app/api/v1/routers/resident_complaints.py`

**Layers** — service `resident_complaints_service` · repository `resident_complaints_repository` ·
schemas `domain/resident_complaint_schemas.py`, `domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/complaints` | `list_my_complaints` :51 | `list_my_complaints_api_v1_complaints_get` | 200 Page_ComplaintSummary_ | § `GET /api/v1/complaints` (API.md:799) |
| `POST /api/v1/complaints` | `raise_complaint` :96 | `raise_complaint_api_v1_complaints_post` | 201 ComplaintDetail | § `POST /api/v1/complaints` (API.md:827) |
| `GET /api/v1/complaints/{complaint_id}` | `get_complaint` :125 | `get_complaint_api_v1_complaints__complaint_id__get` | 200 ComplaintDetail | § `GET /api/v1/complaints/{complaintId}` (API.md:863) |
| `POST /api/v1/complaints/{complaint_id}/reopen` | `reopen_complaint` :158 | `reopen_complaint_api_v1_complaints__complaint_id__reopen_post` | 200 ComplaintDetail | § `POST …/reopen` (API.md:887) |
| `POST /api/v1/complaints/{complaint_id}/resolution` | `confirm_resolution` :189 | `confirm_resolution_api_v1_complaints__complaint_id__resolution_post` | 200 ComplaintDetail | § `POST …/resolution` (API.md:918) |
| `POST /api/v1/complaints/{complaint_id}/read` | `mark_complaint_read` :219 | `mark_complaint_read_api_v1_complaints__complaint_id__read_post` | 200 MessageResult | § `POST …/read` (API.md:936) |

### `backend/app/api/v1/routers/resident_home.py`

**Layers** — service `resident_home_service` · repository `resident_home_repository` · schemas
`domain/resident_home_schemas.py`, `domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/notices` | `list_notices` :31 | `list_notices_api_v1_notices_get` | 200 Page_Notice_ | § `GET /api/v1/notices` (API.md:2796) |
| `GET /api/v1/me/household` | `get_household` :61 | `get_household_api_v1_me_household_get` | 200 HouseholdMember[] | § `GET /api/v1/me/household` (API.md:2809) |
| `POST /api/v1/me/household/phones` | `add_household_phone` :85 | `add_household_phone_api_v1_me_household_phones_post` | 200 HouseholdMember[] | § `POST /api/v1/me/household/phones` (API.md:2822) |
| `GET /api/v1/directory/contacts` | `list_contacts` :111 | `list_contacts_api_v1_directory_contacts_get` | 200 ManagementContact[] | § `GET /api/v1/directory/contacts` (API.md:2841) |

### `backend/app/api/v1/routers/resident_money.py`

**Layers** — service `resident_money_service` (+ `payment_simulator`) · repository
`resident_money_repository` · schemas `domain/resident_money_schemas.py`,
`domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/invoices/mine` | `list_my_invoices` :38 | `list_my_invoices_api_v1_invoices_mine_get` | 200 Page_ResidentInvoice_ | § `GET /api/v1/invoices/mine` (API.md:2713) |
| `POST /api/v1/invoices/{invoice_id}/pay` | `pay_invoice` :76 | `pay_invoice_api_v1_invoices__invoice_id__pay_post` | 200 PaymentOutcome | § `POST /api/v1/invoices/{invoiceId}/pay` (API.md:2738) |
| `GET /api/v1/amenity-bookings/mine` | `list_my_bookings` :119 | `list_my_bookings_api_v1_amenity_bookings_mine_get` | 200 Page_ResidentBooking_ | § `GET /api/v1/amenity-bookings/mine` (API.md:2766) |
| `POST /api/v1/amenity-bookings/{booking_id}/pay` | `pay_booking` :148 | `pay_booking_api_v1_amenity_bookings__booking_id__pay_post` | 200 PaymentOutcome | § `POST /api/v1/amenity-bookings/{bookingId}/pay` (API.md:2775) |

### `backend/app/api/v1/routers/resident_snapshot.py`

**Layers** — service `resident_snapshot_service` (fans out to the other resident services) · schemas
`domain/resident_snapshot_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/resident/snapshot` | `resident_snapshot` :24 | `resident_snapshot_api_v1_resident_snapshot_get` | 200 ResidentSnapshot | § `GET /api/v1/resident/snapshot` (API.md:2880) |

### `backend/app/api/v1/routers/resident_visitor_passes.py`

**Layers** — service `resident_visitor_passes_service` · repository
`resident_visitor_passes_repository` · schemas `domain/resident_visitor_schemas.py`,
`domain/common_schemas.py`, `domain/schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/visitor-passes` | `list_my_visitor_passes` :34 | `list_my_visitor_passes_api_v1_visitor_passes_get` | 200 Page_VisitorPass_ | § `GET /api/v1/visitor-passes` (API.md:2491) |
| `POST /api/v1/visitor-passes` | `create_visitor_pass` :69 | `create_visitor_pass_api_v1_visitor_passes_post` | 201 VisitorPassCreated | § `POST /api/v1/visitor-passes` (API.md:2509) |
| `GET /api/v1/visitor-passes/{pass_id}` | `get_visitor_pass` :101 | `get_visitor_pass_api_v1_visitor_passes__pass_id__get` | 200 VisitorPass | § `GET /api/v1/visitor-passes/{passId}` (API.md:2558) |
| `POST /api/v1/visitor-passes/{pass_id}/approve` | `approve_visitor_pass` :123 | `approve_visitor_pass_api_v1_visitor_passes__pass_id__approve_post` | 200 VisitorPass | § `…/approve` · `/reject` (API.md:2566) |
| `POST /api/v1/visitor-passes/{pass_id}/reject` | `reject_visitor_pass` :153 | `reject_visitor_pass_api_v1_visitor_passes__pass_id__reject_post` | 200 VisitorPass | § `…/approve` · `/reject` (API.md:2566) |
| `POST /api/v1/visitor-passes/{pass_id}/cancel` | `cancel_visitor_pass` :172 | `cancel_visitor_pass_api_v1_visitor_passes__pass_id__cancel_post` | 200 VisitorPass | § `POST …/cancel` (API.md:2579) |

### `backend/app/api/v1/routers/settings.py`

**Layers** — service `settings_service` · repositories `settings_repository`, `tenancy_repository` ·
schemas `domain/settings_schemas.py`

| Operation | Handler | `operationId` (yaml anchor) | Success schema | API.md |
|---|---|---|---|---|
| `GET /api/v1/settings` | `get_settings` :56 | `get_settings_api_v1_settings_get` | 200 SettingsSnapshot | § `GET /api/v1/settings` (API.md:2188) |
| `PUT /api/v1/settings` | `update_settings` :75 | `update_settings_api_v1_settings_put` | 200 SettingsSnapshot | § `PUT /api/v1/settings` (API.md:2274) |

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
| `backend/app/domain/*.py` | Every Pydantic model here becomes a `components.schemas` entry — 131 of them today |
| [`backend/tests/test_openapi_spec.py`](../backend/tests/test_openapi_spec.py) | Runs `--check` inside the suite, so a stale spec fails CI |

---

## 5. Known gaps, as of `98d557a`

These are the reasons this file exists. Everything below is **documented-but-imprecise**, not
missing: all 99 operations are in the spec, with correct paths, methods, request bodies and status
codes. What is wrong is the *body* description on eleven of them, and the *prose coverage* on nine.

### 5.1 Success bodies the spec does not describe

| Operation | What the spec says | What the code returns | Verdict |
|---|---|---|---|
| `GET /api/v1/auth/methods` | 200 `{}`, statuses `200 422 500` | `{"primary": "google", "methods": [{"id","kind","label","enabled"}]}`, an `ETag`, and a **304** to a matching `If-None-Match` | **Defect.** The response models `AuthMethodsResponse` and `AuthMethod` are absent from `components.schemas` entirely, and 304 is undocumented. The handler returns a raw `Response`/`JSONResponse` with no `response_model`, so FastAPI has nothing to emit. The sign-in screen calls this before rendering |
| `POST /admin/access-requests/{id}/approve` · `/reject` · `/blacklist` | 200 free-form object | Raw Postgres RPC output | Under-documented. `-> dict` annotations |
| `POST /dashboard/amenities`, `PUT` and `DELETE /dashboard/amenities/{id}` | 200 free-form object | The raw DB row; `DELETE` returns `{"id": …}` | Under-documented, and the row **differs by deployment** — `dashboard_repository` builds a different shape when `schema_generation() == "legacy"`. There is no single true schema to document until that branch is resolved |
| The four OAuth `307`s | 307, no `Location` header documented | `RedirectResponse` | Minor. The body is genuinely empty; only the header is missing |

### 5.2 Operations with no API.md coverage

Nine operations have no reference section, and two more are named only in passing prose. API.md's
header states that every `###` heading corresponds to a real operation — which is true and is checked
— but the reverse has never been checked, and this is what it hides.

| Family | Operations | Where they appear today |
|---|---|---|
| Access requests | all 7 | One prose sentence at API.md:709 and one traceability row at §16.6 |
| `GET /communities/search`, `GET /communities/admin/units` | 2 | §16.6 row only |
| `PUT` and `DELETE /dashboard/amenities/{id}` | 2 | Nowhere; `POST` gets a §16.6 row |

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

4. Add the row here, under the file that registers the route.
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
cd backend && python scripts/api_map_scan.py
```

[`api_map_scan.py`](../backend/scripts/api_map_scan.py) asks the five questions this file exists to
answer — is every live operation in the spec and vice versa, does each one describe its success body
with a named component, does `API.md` document it, is it listed here, and **do the three records of
each user story's verdict agree** — and prints one line per finding with the source file and line.
`--strict` exits non-zero, for a hook or CI.

That fifth question reports `STORY VERDICT` when `USER_STORIES.md`, `API.md` §16 and
`api_annotations.py` disagree about a story, and `STORY UNBACKED` when a story credited as served or
partial has no operation declaring it. Both were real on 2026-08-08 — six of the first and one of the
second — and neither was visible to any check that existed.

**A finding is not automatically a defect.** As of `98d557a` the scan reports **20**: the eleven
untyped bodies and nine undocumented operations in §5, every one of which already carries a verdict.
All 24 stories agree across all three records.
That is the point of §5 — anything the scan reports that is *not* recorded there is new, and needs a
verdict written in the same pass. An undocumented endpoint nobody wrote down is indistinguishable
next month from one deliberately left free-form.

### 6.3 Verification commands used to build this file

```bash
cd backend && python scripts/export_openapi.py --check && python scripts/api_map_scan.py && python -m pytest -q
```

---

## 7. Change log for this file

| Date | Change |
|---|---|
| 2026-08-09 | Rescanned at `main` @ `1138f2e`, four commits ahead of where the last scan ran. Operation-side findings unchanged at 20, story findings zero, 694 tests passing. One real catch: `7d830e1` routed `POST /onboarding/community` through `pg_errors.translate` and widened its error surface to include 422 without moving a route or a response model — invisible to `--check`, and the case §6.2 step 1 cannot see. Declared in [`api_annotations.py`](../backend/scripts/api_annotations.py) and regenerated |
| 2026-08-08 | §6.1 gains step 5 and §6.2 a fifth question, after a user-story sweep found the verdict for six stories stale in [`product/USER_STORIES.md`](product/USER_STORIES.md) and one story (`US-3.1`) credited as partial by prose that no operation declared. The operation-side findings are unchanged at 20 |
| 2026-08-08 | Created at `main` @ `98d557a`, after a full backend↔spec audit prompted by a testing-team report that the yaml looked out of sync. It was not: the spec regenerates byte-identical and all 99 operations match in both directions. The real gaps are the eleven imprecise success bodies and nine undocumented operations in §5 |
