# 16. The separate-account rule only looks one way

**Labels:** `product-decision`, `auth`, `database`
**Found:** 2026-08-12, auditing the merged service-professional auth commits (`fc69d3f`)
**Urgency:** Before a professional base exists to hit it — the state is unreachable today only
because almost nobody is registered

> **✅ Resolved 2026-08-12, by PO ruling, same day:** *registered professionals are assumed not to
> be living in any association* — the rule is **identity separation**, and the "plumber who lives
> here" case is decided: two accounts. Enforced forward in
> `20260812113000_professional_membership_symmetry.sql`: `enforce_professional_membership_mode`
> now refuses a `resident`/`manager`/`admin` membership on a profile holding a `service_providers`
> row (`HBSEP` → 409 `professional_account_separate`), mirroring the registration-time refusal —
> no `status` filter on the provider row, unknown future roles refused by default. The refusal also
> moved to where the person is: `POST /access-requests` refuses a professional at request time
> rather than days later in an admin's queue, and an invite claim surfaces the real sentence
> instead of a 500. Pre-existing violations are counted and reported by the migration, never
> repaired — which identity to keep is the account holder's decision.
>
> **Two knowingly-accepted residuals:** `register_service_provider` still raises `HB409` for its
> half of the rule (re-declaring an applied function to change an errcode wasn't worth the drift
> risk), and a professional provisioned as a manager by email silently fails to claim on sign-in —
> the claim swallow is deliberate, and per the ruling that person needs a different account.

---

## Body

The service-professional contract says an existing resident/admin/manager identity is told to use a
**separate account** to register as a professional, and both guards enforce exactly that — at
registration time, in that direction:

- the registration RPC refuses a profile that already holds a community membership
  (`20260811162409_service_professional_onboarding.sql:87-98`);
- the frontend routes an already-membered identity away from the professional flow
  (`frontend/src/routes/authRoutes.js:90-94`).

**Nothing watches the other direction.** A professional who registers *first* and then joins a
community as a resident — invite token and all — ends up as one account holding both identities:
precisely the state the contract forbids, reached in the order neither guard checks. The database
trigger that looks like it should catch this, `enforce_professional_membership_mode`
(`…162409:319-351`), only refuses **worker↔security** coexistence; a `resident` membership on a
professional account sails through.

## Why this is a product question, not a bug fix

Symmetric enforcement has a real casualty: **a plumber who genuinely lives in an apartment
community**. If the rule exists for *session routing* (one account, one portal), the asymmetry may
be acceptable — `_portal_for` will send that account somewhere deterministic, and the cost is a
mildly confusing home screen. If the rule exists for *identity separation* (a professional's
provider row, coordinates and hiring history must never share an account with a resident's household
and payment data), then the gap is a genuine hole and the fix belongs in
`enforce_professional_membership_mode`, extended to refuse resident/admin memberships on a
registered professional account — with the "plumber who lives here" case explicitly decided, not
discovered.

What it should not be is decided silently by whoever next touches the trigger.

## How to confirm

```sql
-- with a registered service provider's profile id:
select 1 from public.service_providers where profile_id = :pid;  -- row exists
-- then join a community as a resident with that same account: nothing refuses it.
```

Static: read `enforce_professional_membership_mode` and note the roles it checks.

## Related

- [15 — The service-professional intent dies in the confirmation email](15-the-service-professional-intent-dies-in-the-confirmation-email.md) —
  same audit
- `docs/plans/SERVICE_PROFESSIONAL_AUTH_IMPLEMENTATION.md` — the locked contract this reading is of
