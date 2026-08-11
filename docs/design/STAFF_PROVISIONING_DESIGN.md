# Staff provisioning — how a manager or supervisor comes to exist

**Status** designed and built, `0049_staff_provisioning.sql` · **Date** 2026-08-11
**Touches the auth seam** — `app/services/auth_service.py`, which belongs to the auth workstream.
This document exists because that file is not changed without one. Raised for the auth owner in
`docs/FRONTEND_MEETING_AGENDA.md`.

---

## The ruling

> "There is no registration process for the manager or supervisor. The manager is created by the
> admin and the OAuth goes through based on the manager email that is given in the creation process.
> The supervisor is either created by the admin or the manager and there is no registration process
> but only through the creation of the same by either of them. The servicemen (of technician rank in
> the hierarchy) are the only ones in the whole service section who have a registration process of
> their own."

So the service section has exactly two ways in, and they are deliberately asymmetric:

| | Servicemen | Leadership |
|---|---|---|
| Who initiates | The person | An administrator (or a manager, for a supervisor) |
| Registration | `service_providers` (`0034`), self-service | **None** |
| Negotiation | `service_applications` (`0035`) — apply or be invited, then a decision | **None** |
| Admitted when | A manager accepts | They sign in with the address that was typed |
| Rank | `member` | `manager` or `supervisor` |

## Why this needs a migration rather than an endpoint

`get_session_context` resolves a membership by `profile_id`. At the moment an administrator creates
a manager **there is no profile**: that person has never signed in, and Supabase mints the `profiles`
row on first sign-in. There is nothing to attach a membership to.

So the provisioning is stored against the **email** and claimed on first sign-in.

```
admin fills the form
  └─ POST /departments/{id}/staff-invitations
       └─ invite_staff_member(...)          → staff_invitations row, status 'pending'

…later, that person signs in with Google…

GET /auth/session
  └─ get_session_context
       ├─ profile found or created (upsert_profile writes display_email)
       ├─ _active_memberships → none
       ├─ _claim_staff_invitations(verified email)
       │    └─ claim_staff_invitations(profile_id, email)   [service role only]
       │         ├─ community_memberships row (role derived, see below)
       │         ├─ staff_assignments row    (rank, job_title, name, phone)
       │         └─ staff_invitations → 'claimed'
       └─ _active_memberships → the new one → _portal_for → /manager
```

## Why not `resident_invites`

It was the obvious move and it is the wrong one. `resident_invites` already binds an email, already
carries `intended_role`, and `membership_role` already contains `manager`. But it requires a
**token and a code** — both `NOT NULL`, both `UNIQUE` — and `redeem_pending_invitation` checks the
email *on top of* the token (`invitation_service.py:103`).

That token is a deliberate second factor and the standing rule is that it stays mandatory. Widening
the table to make it optional would weaken the resident flow to serve a different flow's
requirement. Leadership gets its own table; **the resident rule is untouched.**

## The trade-off, stated rather than softened

**Email alone is one factor.** Whoever controls that mailbox at first sign-in becomes the manager of
that department. There is no code to intercept and no link to forward, so the exposure is narrower
than a mailed token — but it is real, and *the administrator typing the address correctly is the
only check.*

Two consequences worth designing around, both of which the build does:

- **A wrong address fails silently.** Nothing is mailed, so there is no bounce and no error — only an
  invitation that stays `pending` forever. That is why `GET /departments/{id}/staff-invitations`
  returns pending rows and the department screen shows them: it is the only place a typo is visible.
- **A claimed invitation is kept and shown.** An administrator needs to distinguish "still expected"
  from "has been working for a month", and a list that dropped people on arrival would look identical
  either way.

If the auth owner wants a second factor here later, the shape that fits is a nonce on the invitation
plus a one-time link — which is `resident_invites` again, and would be a change to this table, not to
that one.

### Put to the product owner on 2026-08-12, and declined

A short claim code — one column, generated at creation, shown once to the administrator, typed at
first sign-in — was offered as the closing fix and **turned down**:

> *"lets assume that the admin wont make any typos for now and if the admin wants he can change the
> email when he notices via an edit option."*

So the single factor stands, and the recovery path was built instead:
`PATCH /departments/{id}/staff-invitations/{invitationId}`, backed by
`update_staff_invitation`. Email, name, phone, job title and rank are all correctable while the
invitation is `pending`.

**The department is not correctable**, and the omission is load-bearing rather than an oversight:
`can_manage_department` authorizes this call against the invitation's *current* department, so
allowing a move would let the manager of department A mint staff into department B without B's
manager being asked. Moving an invitation is revoke-and-reissue under the authority of wherever it is
going.

**What this changes about the exposure, and what it does not.** It makes the *accident* recoverable —
an administrator who notices a stale `pending` row can now fix it in place instead of withdrawing and
retyping, which used to throw away who issued the original and when. It does **nothing** about the
security case: an address that is wrong *and* belongs to somebody who signs into HomeBandhu still
admits that person, and still does so silently. The pending list remains the only detector, and it
only detects the case where nobody claims.

## Membership role is derived, never stored

Rank and role are separate axes (D3). The invitation stores the **rank**; the role is computed at
claim time from the department's `kind`, the same derivation `decide_service_application` does
(`0035:918-922`).

| `rank` | department `kind` | membership role | lands in |
|---|---|---|---|
| `manager` | `service` | `manager` | `/manager` |
| `manager` | `security` | `manager` | `/security-manager` |
| `supervisor` | `service` | `worker` | `/worker` |
| `supervisor` | `security` | `security` | `/security-manager` |

Deriving late rather than storing means a department that changes kind between the invitation and the
sign-in cannot mint a membership pointing at the wrong portal.

The two `security` rows are not new policy: `_portal_for` already routes a `security` membership
whose roster rank is `manager` or `supervisor` to `/security-manager`, because that is
`gate_admin_community_for` — the live guard on posts CRUD and shift scheduling — asked from the other
side.

**`member` is not a valid rank on an invitation.** That rank is reached only by hiring a registered
service provider, which is the point of removing typed-in technicians from the department form.

## Authorization

| Action | Who | Enforced by |
|---|---|---|
| Create a manager | Admin of the community, or the department's manager | `can_manage_department` (`0035:458`) |
| Create a supervisor | The same — **which is what lets a manager create one without being an admin** | the same predicate |
| Withdraw an unclaimed invitation | The same | the same predicate |
| Claim | Nobody, directly | `claim_staff_invitations` is **revoked from `authenticated`** |

`can_manage_department` also permits a manager to create a *second* manager. That is refused at claim
time by `staff_assignments_one_active_manager` (`0035:115`), and refusing it there is deliberate: an
invitation is not yet a roster row, and two invitations racing to be claimed is a database question,
not an API one.

### The one function authenticated users may not call

`claim_staff_invitations(profile_id, email)` takes the email as an argument, and **the email is the
authorization**. A signed-in user who could call it with somebody else's address would admit
themselves to that person's department. So:

- `revoke all … from public, anon, authenticated` — service role only.
- The Python caller passes `verified_identity(access_token).email`, which asks GoTrue. It does not
  trust `profiles.display_email` alone: that is an ordinary table, and treating a table as the
  authority on who somebody is would make a row a credential.

### Failure is swallowed, on purpose

`_claim_staff_invitations` catches and returns `False`. Claiming is an *enhancement* to a session
that is already valid — somebody provisioned who hits a database error should land on the account
page and be admitted on their next sign-in, not be refused a session they are entitled to.

## Idempotence

`get_session_context` runs on every session read, not only the first. `claim_staff_invitations`:

- selects only `status = 'pending'`, so a second call finds nothing and returns zero rows;
- **skips** (rather than fails) an invitation whose community the profile already belongs to, leaving
  it `pending` — which is true, and which an administrator can see;
- is guarded by `staff_invitations_claim_check`, so a half-written claim cannot look like a live
  invitation and be claimed again.

The claim is attempted **only on the path that has already established there is no membership**, so
the ordinary signed-in request pays nothing for it.

## What this does not do

- **No email is sent.** There is no mail transport in this project and this feature does not add one.
- **No notification.** The person being provisioned has no account to notify.
- **No self-service.** A manager cannot appoint themselves; every row records
  `created_by_membership_id`.
- **It has never run.** No migration in this repo has been applied to any database. The claim path in
  particular cannot be truly proven until a second real account signs in with a provisioned address;
  until then it is covered by unit tests over the seam and a `pglast` parse of the SQL.

## Related

- `backend/supabase/migrations/0049_staff_provisioning.sql` — the header carries the same reasoning
  next to the code
- `docs/API.md` §18 — the three endpoints
- `docs/changelogs/2026-08-11-departments-skills-and-connectivity.md` — phase 2
- `docs/CONFLICT_RESOLUTIONS.md` D3 — rank and role as separate axes
