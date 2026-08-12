# 11. The naming contract in `API.md` §1.3 is wrong: 28 snake_case fields sit outside its stated exception

**Labels:** `documentation`, `api`, `consistency`
**Found:** 2026-08-11, by the end-to-end compatibility sweep
**Urgency:** Low risk, but it is a *contract* document giving a wrong answer — fix the sentence, not the code

---

## What the contract is, and where it lives

Two artifacts publish the wire format, and this issue is about the first disagreeing with the second.

| Artifact | What it is | Where |
|---|---|---|
| **The prose contract** | [`docs/API.md`](../API.md) **§1.3 — "Field naming — a known inconsistency"** (line 146) | hand-written, and the thing a human reads before writing a client |
| **The generated contract** | [`docs/openapi.yaml`](../openapi.yaml), `components/schemas` | emitted from the Pydantic models by `backend/scripts/export_openapi.py`, so it cannot disagree with the code |

§1.3 states the rule in a two-row table:

| Endpoint group | Case | Example |
|---|---|---|
| `/auth/*`, `/admin/invitations` | `snake_case` | `token_hash`, `invitee_email`, `intended_unit_id` |
| Everything else | `camelCase` | `pageSize`, `timeAgo`, `unitId` |

followed by the reasoning: *"This is not a style preference, it is a seam… The auth DTOs predate that
constraint, and the frontend already reads them as `snake_case`."*

## Body

The generated contract holds **48 snake_case schema properties**. Twenty of them are inside the
declared exception and the rule describes them correctly. **The other 28 are not `/auth/*` and not
`/admin/invitations`**, so §1.3's second row — *"Everything else: camelCase"* — is false for seven
schemas across three surfaces that have nothing to do with authentication:

| Schema | Surface | snake_case properties |
|---|---|---|
| `CommunityOnboardingRequest` | `POST /communities/onboarding` | `address_line1`, `address_line2`, `admin_profile`, `block_locations`, `community_type`, `country_code`, `enabled_features`, `postal_code`, `villa_locations` |
| `AccessRequestResponse` | `/access-requests`, `/admin/access-requests` | `applicant_email`, `applicant_name`, `applicant_phone_e164`, `created_at`, `rejection_reason`, `requested_relationship`, `requested_unit_id`, `reviewed_at` |
| `AmenityWrite` | `POST`/`PUT /amenities` | `approval_required`, `booking_mode`, `hourly_rate`, `is_active` |
| `CreateAccessRequest` | `POST /access-requests` | `community_id`, `requested_relationship`, `requested_unit_id` |
| `CommunityUnitOption` | `GET /communities/{id}/units` | `building_name`, `unit_code` |
| `ApproveAccessRequest` | `POST /admin/access-requests/{id}/approve` | `unit_id` |
| `CommunitySearchItem` | `GET /communities/search` | `community_type` |

For completeness, the 20 the rule *does* cover: `CreateInvitationRequest` (3), `InvitationCreated`
(5), `EmailTokenRequest` (2), `MembershipContext` (3), `PasswordSignUpRequest` (2),
`PasswordSignInRequest` (1), `PasswordResetRequest` (1), `Profile` (2), `SessionContext` (1).

**Query and header parameters are clean.** Zero snake_case among them — `GET /security/posts` was the
last one and it was given an `includeInactive` alias when the gate portal was built. So this is
entirely about body properties.

## Why the fix is the document and not the code

**The code is internally consistent, and the frontend already speaks these names.** Spot-checked
against `frontend/src`:

| Field | Read or written at |
|---|---|
| `community_id`, `requested_relationship` | `features/registration/components/JoinCommunityTab.jsx:42-43` — the payload is *built* in snake_case |
| `full_name` | 15 sites |
| `onboarding_eligible` | 4 sites |
| `address_line1`, `community_type`, `hourly_rate`, `approval_required`, `applicant_name`, `unit_code` | one site each |

So nothing is broken at runtime, and renaming these 28 would break working screens for a style rule.

**What is actually wrong is that §1.3 is the file somebody consults to answer "what case is this
field?", and it gives a confident wrong answer for three whole surfaces.** That is the same failure
mode as issue 2 in this directory (`roles.py` documenting an RBAC model the code no longer used):
not dead text, but text that will be *believed*. A developer writing the amenity admin screen reads
§1.3, sends `hourlyRate`, and gets a 422 whose message names a field their contract said would not
exist.

It also mis-states the reason. §1.3 explains snake_case as a legacy of "the auth DTOs" — but
`AmenityWrite` and `CommunityOnboardingRequest` are not auth DTOs, so the real rule is *older
surfaces are snake_case regardless of what they do*, which is a materially different thing to tell
someone planning a cleanup.

## How to confirm

```bash
cd backend && python -c "
import re, yaml, pathlib
snake = re.compile(r'^[a-z][a-z0-9]*(_[a-z0-9]+)+$')
spec = yaml.safe_load(pathlib.Path('../docs/openapi.yaml').read_text(encoding='utf-8'))
for name, schema in (spec['components']['schemas'] or {}).items():
    for prop in (schema.get('properties') or {}):
        if snake.match(prop): print(f'{name}.{prop}')
"
```

Prints 48 lines. Compare the schema names against the two groups §1.3 names.

## Suggested fix

**Rewrite §1.3; change no code.** Three edits:

1. Replace the endpoint-group table with one keyed on *schema*, or state the rule as it really is:
   *snake_case on the pre-camelCase surfaces — auth, invitations, access requests, community
   onboarding and the amenity admin write — camelCase everywhere else*, and name them.
2. Correct the explanation. "The auth DTOs predate that constraint" is true and incomplete; the
   boundary is chronological, not functional.
3. Cross-link this file, so the count is checkable rather than asserted.

Then decide the underlying question **once**, and write the decision down either way — that is what
[issue 8](README.md#8-auth-speaks-snake_case-everything-else-speaks-camelcase) already asks for, and
this issue widens its scope from "the auth seam" to "five surfaces". Converting is a coordinated
two-sided change touching working screens; declaring the seam permanent is free. What is not
acceptable is a contract document that describes neither.

## Related

- [8 — `/auth/*` speaks `snake_case`, everything else speaks `camelCase`](README.md#8-auth-speaks-snake_case-everything-else-speaks-camelcase)
  — the same seam, seen when it was believed to be auth-only. **This issue supersedes its scope.**
- [2 — `roles.py` documents an RBAC model the code no longer uses](README.md#2-rolespy-documents-an-rbac-model-the-code-no-longer-uses)
  — the same failure mode, resolved
