# `docs/erd/` — which file is which

Two DBML files live here and they are **not** interchangeable.

| File | What it is | Status |
|---|---|---|
| `homebandhu-v1-milestone1.dbml` | The **milestone-1 submission ERD**, 48 tables. Verified byte-identical to the team's supplied `er-dbml.txt` on 2026-07-29. | **Authoritative.** Owned and maintained by the teammates handling the ERD. |
| `homebandhu.dbml` | A **v2 draft** produced during backend planning, **66 table blocks** as of 2026-08-12 (63 when this file was written; `complaint_department_requests`, `department_skills` and `staff_invitations` have been added since). Resolves many known defects in v1 (see `../MILESTONE1_ARTIFACT_ISSUES.md`) but was never agreed as the team artifact. | **Working draft only.** Do not treat as authoritative. |

> **The v2 draft is not a mirror of what is built, and must not be read as one.**
> Its header calls itself a projection of `backend/supabase/migrations/`; it is
> not, and has not been since the service-operations work began. It is missing
> ~37 implemented tables (`service_providers`, `work_orders`' dispatch tables,
> the security-gate tables, `dm_threads`, …), carries ~27 tables that were never
> built (`otp_challenges`, `committee_positions`, `work_order_proposals`, …), and
> its `membership_role` enum is `resident | staff | admin` where the
> implementation uses `resident | worker | security | manager | admin`. What it
> receives are **design** decisions, table by table, when one is taken. The file
> that tracks the implemented schema is
> [`../diagrams/homebandhu_submission_erd.dbml`](../diagrams/homebandhu_submission_erd.dbml),
> and that is the one to reconcile against a migration.

**Apostrophes.** DBML single-quoted strings have no escape: `'…manager''s inbox…'`
is a parse error, not an escaped quote, and it takes the whole file down with it.
Use the triple-quoted form `Note: '''…'''` when the wording needs one. This bit
`homebandhu.dbml` on 2026-08-12 (the file would not parse at all) and
`../diagrams/homebandhu_submission_erd.dbml` on 2026-08-11 before that.

Known issues in the authoritative v1 file are catalogued in
[`../MILESTONE1_ARTIFACT_ISSUES.md`](../MILESTONE1_ARTIFACT_ISSUES.md) — issues are recorded there
rather than fixed here, because the ERD is maintained elsewhere.

The rendered ER diagram image is generated from the `.dbml` on dbdiagram.io. Whenever the
authoritative file changes, the image needs regenerating from it — the `.dbml` is the source of
truth, the image is a projection.
