# Hosted schema drift — the complaint engine

**Probed:** 2026-08-20, read-only, against the linked hosted Supabase project.
**Branch:** `live-app-fixes`.
**Patch:** [`backend/supabase/migrations/20260820120000_hosted_complaint_column_drift.sql`](../backend/supabase/migrations/20260820120000_hosted_complaint_column_drift.sql).
**Applies by hand.** Runbook in §6.

---

## 0. The answer in one paragraph

Three gaps, all on two tables, all of them *columns*. Not one function is
stale: every complaint-engine RPC exists on the hosted project at the arity its
latest migration gives it, including the seven Complaint Engine v2 migrations of
2026-08-13. The hosted `complaint_events` is missing `payload`, the hosted
`complaints` is missing `aggregate_version`, and the hosted
`complaints.description` carries a `not null` the repository has never declared.
All three are columns that only `0001_baseline.sql` declares — and this project
is not a baseline project.

**Where the patch lives, and why not `backend/supabase/patches/`.**
`backend/supabase/migrations/README.md` is explicit: files through `0047` are
immutable, "all fixes and new features now use forward-only timestamped
migrations", and migrations on this project are applied by hand. That *is* the
convention for a hand-applied schema change, so the patch is a timestamped
migration rather than a new `patches/` directory. On a fresh baseline project
every statement in it is a no-op.

---

## 1. Why the hosted schema looks like this

The linked project **was not created from `0001_baseline.sql`.** Its complaint
tables are the pre-baseline shape that `0020`'s header calls "the legacy
schema":

| Table | Hosted has, baseline never declared |
|---|---|
| `complaint_events` | `previous_status`, `new_status`, `note` (all nullable) |
| `complaints` | `unit_id`, `closed_at` |

Every migration from `0018` onward extends those tables with
`add column if not exists`, so each one applied cleanly against the legacy shape
and each one reported success. What none of them adds is a column that *only*
the baseline declares. There are exactly two on this surface:

* `complaint_events.payload jsonb not null default '{}'::jsonb` (`0001`:70)
* `complaints.aggregate_version integer not null default 1` (`0001`:69)

This is the general shape of the drift on this project, not a complaint-specific
accident. The same probe found `audit_events.payload`, three `communities`
columns, `community_admin_terms.designation` and `amenities.booking_rules`
missing for the same reason, and `amenity_operating_hours`, `media`,
`member_activity`, `idempotency_records` and `rate_limit_buckets` absent as
tables. **None of those are in scope here and none are touched by the patch** —
they are recorded so the next person does not have to rediscover the pattern.
(`staff_skills` and `vendors` are absent on purpose: `0044` drops them.)

---

## 2. Gap 1 — `complaint_events.payload`

**Expected** (`0001_baseline.sql`:70):

```sql
payload jsonb not null default '{}'::jsonb
```

**Found:** absent.

**Evidence.**

* `client.table("complaint_events").select("payload").limit(1)` →
  `{'message': 'column complaint_events.payload does not exist', 'code': '42703'}`
* PostgREST's own OpenAPI description of the hosted table
  (`GET /rest/v1/` with `Accept: application/openapi+json`) lists
  `id, complaint_id, actor_membership_id, event_type, previous_status,
  new_status, note, created_at, actor_label` and nothing else. `required`
  (= `not null`, no default) is `id, complaint_id, event_type, created_at`, so
  the three legacy columns are nullable and an insert that omits them is legal.
* The same call proved `actor_label` present, i.e. `0020` *did* apply here.

**What it breaks.** Every write path in the complaint engine, and one read.
Forty-five `insert into public.complaint_events (... payload)` sites across
twelve migrations. By user-visible action:

| Action | Endpoint | Writer |
|---|---|---|
| Resident files a complaint | `POST /api/v1/complaints` | `raise_complaint` (`20260813100000`:116) — **the observed 400** |
| Resident reopens one | `POST /api/v1/complaints/{id}/reopen` | `reopen_complaint` (`20260812090300`:1107) |
| Resident confirms a resolution | `POST /api/v1/complaints/{id}/resolution` | `confirm_complaint_resolution` (`20260812090300`:1179) |
| Resident cancels or re-pools scheduled work | `POST /api/v1/complaints/{id}/cancel` | `resident_cancel_work` (`20260813103000`:35, 38) |
| Anyone comments | `POST /api/v1/complaints/{id}/comments` | `add_complaint_comment` (`20260812090300`:1256) |
| Admin edits a complaint | `PATCH /api/v1/complaints/{id}` | `update_complaint` (`0031`:731–801) |
| Admin allots a department | `PUT /api/v1/complaints/{id}/department` | `assign_complaint_department` (`20260812090300`:475) |
| Supervisor asks to move one | `POST /api/v1/complaints/{id}/department-requests` | `request_complaint_department_change` (`20260812090300`:632) |
| Manager decides that request | `POST /api/v1/complaints/{id}/department-requests/{rid}` | `decide_complaint_department_change` (`20260812090300`:732, 750) |
| Raise / edit / assign / reschedule / cancel work | the eight `/work-orders` operations | `0036` §§ + `20260812120000` |
| Worker accepts / starts / completes / declines / reports failure | `POST /api/v1/worker/jobs/{id}/…` | `0039`:375, 525, 607, 708; `20260813101000`:116 |
| The dispatcher sweep offers or auto-assigns | background | `0037`:776, 856 |
| A complaint reaching `resolved` | any status write | `on_complaint_resolved` trigger (`20260813104000`:74) |
| The 48h warning and 72h auto-close | background | `dispatch_auto_close` (`20260813104000`:92, 96) |

The read: `resident_complaints_repository.timeline()` selects
`id, event_type, actor_label, payload, created_at`, so **`GET /api/v1/complaints/{id}`
fails too** — the resident detail screen, not just the writes.

---

## 3. Gap 2 — `complaints.aggregate_version`

**Expected** (`0001_baseline.sql`:69): `aggregate_version integer not null default 1`.
**Found:** absent.

**Evidence.**
`client.table("complaints").select("aggregate_version").limit(1)` →
`{'message': 'column complaints.aggregate_version does not exist', 'code': '42703'}`.
Confirmed by the OpenAPI description, which lists 25 columns on `complaints`
and not this one.

**What it breaks.** Four RPCs do `aggregate_version = aggregate_version + 1`
and would each fail 42703 on their first call:

| Action | Endpoint | Writer |
|---|---|---|
| Admin edits a complaint | `PATCH /api/v1/complaints/{id}` | `update_complaint` (`0031`:726) |
| Resident reopens | `POST /api/v1/complaints/{id}/reopen` | `reopen_complaint` (`20260812090300`:1099) |
| Resident confirms | `POST /api/v1/complaints/{id}/resolution` | `confirm_complaint_resolution` (`20260812090300`:1175) |
| Anyone comments | `POST /api/v1/complaints/{id}/comments` | `add_complaint_comment` (`20260812090300`:1264) |

**This is the part that matters for sequencing:** these four are on the *same*
endpoints as gap 1, one statement later. Patching `payload` alone would turn
four 42703s into four different 42703s. Nothing in the observed failure pointed
at this — it was found by probing, not by a stack trace, because gap 1 fails
first for every caller.

`raise_complaint` never touches the column, which is why filing a complaint got
as far as `complaint_events` at all.

---

## 4. Gap 3 — `complaints.description` is `not null` on the host

**Expected** (`0001_baseline.sql`:69): `description text` — nullable.
**Found:** `not null`.

**Evidence.** PostgREST's OpenAPI `required` list for `complaints` is
`id, community_id, raised_by_membership_id, title, description, category,
priority, status, progress_percent, created_at, updated_at, reopened_count`.
`description` is in it; `title` and `category` are too and are correct
(the baseline declares both `not null`). `description` is the odd one, and no
repository migration has ever asked for it.

**What it breaks.** `POST /api/v1/complaints` with no description.
`ComplaintCreate.description` is `_optional_text(4000) = ""`
(`app/domain/resident_complaint_schemas.py`:168), the service passes
`body.description.strip()` (`resident_complaints_service.py`:373), and
`raise_complaint` inserts
`nullif(btrim(coalesce(p_description, '')), '')` — null for the empty string.
The insert into `complaints` then fails 23502, one statement *before* the
`complaint_events` insert that produced the reported 400.

Nobody has hit this yet because gap 1 fails the same transaction for everyone,
including the callers who did supply a description.

**This is the one statement in the patch that removes a constraint rather than
adding a column.** It is still a widening — no row previously accepted is
rejected afterwards — and it moves the hosted column towards the repository's
own declaration. The opposite direction (make a description mandatory on the
wire) is a product question, and it is logged as an open question in
[`COMPLAINT_ENGINE_HANDOFF.md`](COMPLAINT_ENGINE_HANDOFF.md) §11 rather than
decided here.

---

## 5. What was probed and found *correct*

Recorded so the next person does not re-probe it.

**Columns — all present.** `complaint_comments` (7/7, including `author_label`,
`visibility`, and `author_membership_id` nullable), `complaint_read_state` (3/3),
`complaint_categories` (5/5 incl. `skill_id`), `department_categories`,
`department_skills`, `complaint_department_requests` (10/10),
`dispatch_tasks` (12/12 incl. `complaint_id`, `departure_id`, `priority`),
`work_orders` (17/17 incl. `cancelled_by`, `skill_id`, `supervisor_membership_id`),
`work_order_assignments` (12/12 incl. `is_forced`), `skills` (4/4).

**Views — all present with every column their readers select.**
`complaint_overview` (22/22 — the whole `_DETAIL_SELECT` plus `is_overdue`,
`is_unread`, `comment_count`, `last_activity_at`), `my_worker_job` (8/8 incl.
`is_forced`).

**On `complaints` itself, 24 of 25 expected columns are present**, including all
four post-baseline waves: `0019` (`department_id`, `assigned_to_membership_id`,
`assignee_label`, `due_at`), `0031` (`priority`, `location`,
`expected_resolution_at`, `reopened_count`, `resolution_rating`,
`resident_feedback`), `20260813100000` (`skill_id`) and `20260813103000`
(`returned_to_pool_at`).

**Functions — all present, all at the right arity.** Read from PostgREST's
`/rpc/*` path list with its argument schemas, which is a stronger check than an
existence probe because it shows the signature:

```
raise_complaint(8)                       resolve_complaint_department(4)
update_complaint(9)                      add_complaint_comment(5)
reopen_complaint(2)                      confirm_complaint_resolution(3)
mark_complaint_read(2)                   resident_cancel_work(3)
complaint_sla_hours(1)                   notify_complaint_staff(4)
notify_community_staff(4)                notify_community_roles(5)
notify_member(3)                         department_complaints(2)
unassigned_complaints(1)                 staff_complaint_detail(1)
assign_complaint_department(3)           complaint_excluded_staff(1)
request_complaint_department_change(4)   decide_complaint_department_change(4)
enqueue_complaint_dispatch_task(3)       dispatch_auto_close(2)
dispatch_manual_window(1)                dispatch_force_assign(1)
fire_dispatch_task(1)                    create_work_order(8)
is_own_membership(1) · is_community_admin(1) · is_community_member(1)
can_supervise_department(1)
```

`raise_complaint` at 8 and `resolve_complaint_department` at 4 are the
signatures `20260813100000` creates, and `staff_complaint_detail` only exists
from `20260813105000`, so **all seven Complaint Engine v2 migrations are
applied.** No function needs replacing and the patch replaces none.

**Data.** `complaints`, `complaint_events`, `complaint_comments`, `work_orders`
and `dispatch_tasks` each held **0 rows**. So `add column … not null default`
rewrites nothing, and there is no legacy `note`/`new_status` history to
backfill into `payload`.

**Not verifiable through PostgREST, and therefore not patched.** Triggers and
trigger functions have no `/rpc` path and cannot be called: `complaints_sse`,
`complaint_comments_sse`, `complaints_on_resolved`,
`work_orders_project_complaint`, `work_order_assignments_project_complaint`,
`work_orders_terminal_complaint_guard`, `complaints_department_live_work_guard`,
`work_orders_clear_complaint_pool_flag`, `work_order_assignments_open_chat`,
`complaint_categories_link_skill`. Each is created by a migration whose *other*
objects were proved present, and each migration ends with a `do $$ … raise
exception` guard that would have aborted the file, so they are inferred present.
CHECK constraints (`complaint_events_type_check`, `dispatch_tasks_kind_check`)
are inferred the same way. If a complaint write still misbehaves after §6, these
are the next thing to look at, and looking at them needs a SQL console rather
than PostgREST.

---

## 6. Runbook

Read-only probing produced this; applying it is a human's decision. Nothing
below is destructive and steps 1–4 are one file.

### Before

1. Confirm you are on the right project: the Supabase dashboard's project ref
   must match `SUPABASE_URL` in `backend/.env`.
2. Re-run the probe (§7) and check it still reports the same three gaps. If it
   reports none, someone has already applied this and you are done.

### Apply

3. Open the Supabase **SQL Editor** on the linked project.
4. Paste the whole of
   `backend/supabase/migrations/20260820120000_hosted_complaint_column_drift.sql`
   and run it. It is one file, ordered to apply top to bottom, and every
   statement is idempotent — running it twice changes nothing the second time.
5. Expect **Success. No rows returned.** Section 4 of the file re-checks all
   three columns in the same transaction; any `raise exception` means nothing
   was committed and the message names which gap survived.

Statement by statement, with what to undo it:

| # | Statement | Rollback | Safe to roll back while |
|---|---|---|---|
| 1 | `alter table public.complaint_events add column if not exists payload jsonb not null default '{}'::jsonb` | `alter table public.complaint_events drop column payload;` | no timeline entry has been written through it (i.e. no complaint has been filed since) |
| 2 | `alter table public.complaints add column if not exists aggregate_version integer not null default 1` | `alter table public.complaints drop column aggregate_version;` | always — nothing reads it outside the four RPCs |
| 3 | `alter table public.complaints alter column description drop not null` | `alter table public.complaints alter column description set not null;` | no complaint with a null description exists yet |
| 4 | verification `do $$` block | — | writes nothing |

Rolling any of these back restores the broken state; the rollbacks exist for a
mistaken *project*, not a mistaken change.

### Verify

6. Re-run the probe (§7). It must report **no gaps**.
7. Then exercise the app, in this order — each one covers a different writer:
   * **File a complaint with no description** (`POST /api/v1/complaints`). This
     is the reported failure and it covers all three gaps at once: the
     `complaints` insert (gap 3), the `complaint_events` insert (gap 1). It must
     return 201 and the complaint must appear in the resident's list.
   * **Open it** (`GET /api/v1/complaints/{id}`). The timeline must render a
     `raised` entry — that is the `payload` *read* in
     `resident_complaints_repository.timeline()`.
   * **Comment on it** (`POST /api/v1/complaints/{id}/comments`). Covers gap 2
     (`add_complaint_comment` increments `aggregate_version`) and gap 1 again.
   * **Edit it as an admin** (`PATCH /api/v1/complaints/{id}`) with a status
     change. Covers `update_complaint`, the other `aggregate_version` writer,
     and the `status_changed` event.
   * **Check the admin dashboard snapshot still loads.** It reads
     `complaint_events(id, event_type, note, new_status, created_at)` — this
     project takes `dashboard_repository.py`'s **legacy** branch, because
     `visitor_access_requests` exists here and that is the branch's feature
     test. The patch adds a column and drops none, so this must be unaffected;
     it is on the list because it is the read that would notice if someone
     "tidied up" the legacy columns.

If the first step still fails, capture the SQLSTATE from
`app/core/pg_errors.py`'s `translate()` fallback log — a 42703 naming a
different column means more drift of the same kind; a 42P01 or an error from a
trigger function means the unverifiable objects in §5 need a SQL console.

---

## 7. The probe

Read-only. Column existence, plus PostgREST's own description of the hosted
schema — which is the stronger of the two, since it reports nullability,
defaults and every RPC's argument list without touching a row.

```python
import sys, json, urllib.request
sys.path.insert(0, r"…\MAY2026-Team-035\backend")
from app.core.supabase_client import get_service_client
from app.config import get_settings

c = get_service_client()

# 1. the three gaps, directly
for table, col in [("complaint_events", "payload"),
                   ("complaints", "aggregate_version")]:
    try:
        c.table(table).select(col).limit(1).execute()
        print(f"OK  {table}.{col}")
    except Exception as exc:
        print(f"GAP {table}.{col}: {exc}")

# 2. nullability and every RPC signature, from PostgREST itself
s = get_settings()
key = s.supabase_service_role_key
req = urllib.request.Request(
    s.supabase_url.rstrip("/") + "/rest/v1/",
    headers={"apikey": key, "Authorization": f"Bearer {key}",
             "Accept": "application/openapi+json"})
spec = json.load(urllib.request.urlopen(req))
print("description not null:",
      "description" in spec["definitions"]["complaints"]["required"])
```

Run it with `backend/.venv/Scripts/python.exe` from `backend/`. An `APIError`
naming the column is the missing-column signal; `PGRST202` from an `.rpc()`
call is the missing-function one.

**The rule this probing followed, and the next person should too:** an RPC is
probed for *existence* with arguments that cannot pass its own guards — a random
UUID membership, a random complaint id — so the function raises its own
`HB403`/`HB404`/`P0002` before it reaches a write. Never call a complaint RPC
with arguments that could succeed.
