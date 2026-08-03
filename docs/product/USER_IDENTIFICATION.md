# User identification

> **Source.** Team 035, `user-identification.txt`. Reproduced verbatim; headings and the `UT-*`
> identifiers are the only additions. See [`README.md`](README.md).

## UT-1 — Primary users

These are the main users of the HomeBandhu application. They interact with the application on a
daily basis and rely on it to perform essential residential and administrative tasks. The system is
primarily designed to support their needs, including communication, maintenance management,
payments, visitor management, and access to community services. Since they use the application most
frequently, their experience directly impacts the effectiveness of the apartment management system.

- Apartment Residents / Owners
- Tenants
- Association Committee Members (President, Secretary, Treasurer)

## UT-2 — Secondary users

These users are operational staff who support the daily functioning and maintenance of the apartment
community. They use the system to manage facilities, coordinate maintenance activities, oversee
security, and ensure smooth execution of operational tasks. Although they are not core users of the
application, they play an important role in maintaining efficient apartment operations.

- Facility Managers
- Housekeeping Supervisors
- Security Manager
- Maintenance Staff
- Administrative Staff

## UT-3 — Tertiary users

These users are external stakeholders and support personnel who interact with the system
occasionally or indirectly. They provide specialized services, technical support, auditing,
infrastructure, or construction-related assistance. Their access to the system is usually limited to
specific tasks or events, but they contribute to the overall functioning, reliability, and long-term
management of the apartment community.

- Vendors (electricians, plumbers, water suppliers)
- Event Coordinators
- Software Developers
- Security Service Providers
- Apartment Builders
- Local Service Providers
- Internet / Cloud Providers
- Auditors

---

## How these tiers land in the implemented role model

Added by the backend workstream; **not part of the team's source document**. It is recorded here
because the mapping is not one-to-one and the mismatch is worth seeing before it surprises someone.

| Tier | Person | Backend representation |
|---|---|---|
| UT-1 | Resident / Owner, Tenant | `community_memberships` row with `role = 'resident'`. Owner vs tenant is **not** on the membership — it is `unit_residencies.relationship_type`, one of `owner`, `tenant`, `family_member`, `caregiver`, `other` |
| UT-1 | Committee member (President, Secretary, Treasurer) | `role = 'admin'`. The three offices are **not** separate roles — `community_admin_terms` records only who holds the community's single designated admin office, guarded by the `community_admin_one_active` partial unique index |
| UT-2 | Facility Manager, Housekeeping Supervisor, Security Manager, Maintenance Staff | `staff_assignments` rows, read through the `department_staff_overview` view. `membership_id` is **nullable** (`0019` drops the `not null`), so a staff member is a name on a roster, not an account |
| UT-2 | Administrative Staff | `role = 'admin'`, same as a committee member |
| UT-3 | Everyone | **No representation at all.** Vendors appear only as free text in a `staff_assignments.display_name` or a complaint's `assignee_label` |

The `membership_role` enum does carry `worker`, `security` and `manager` alongside `resident` and
`admin`, so the tiers are *nameable*. Nothing issues those memberships today — no endpoint creates
one, and `POST /departments/{id}/staff` deliberately leaves `membership_id` null.

Two consequences that follow from that table and are easy to miss:

1. **A staff member cannot log in.** Every story written for a Facility Manager or Security Manager
   is therefore a story about an *admin acting on their behalf*, or a story with no home. §14 of
   [`../API.md`](../API.md#14-user-stories--endpoints) marks which.
2. **Committee offices are indistinguishable at the API.** A Treasurer and a Secretary present
   identical credentials, so nothing can be restricted to one of them. If the product needs
   "only the Treasurer may record a payment", that is a schema change, not a guard.
