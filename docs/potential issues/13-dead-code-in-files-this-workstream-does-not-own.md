# 13. Dead code and a 2.6 MB tool output, in files nobody is deleting

**Labels:** `tech-debt`, `cleanup`
**Found:** 2026-08-11, by the first run of `scripts/dead_code_sweep.py`
**Urgency:** Low, individually. The reason to write it down is that nothing else will

---

## Body

A repeatable sweep now exists for the four questions no tool in this project
asks — unreferenced modules, unused exports, unreferenced backend names, and
Markdown links that resolve to nothing:

```bash
cd backend && python scripts/dead_code_sweep.py
```

Its first run found dead code in three files this workstream owns, which was
deleted rather than filed. Everything below is the remainder: real findings in
files belonging to other people, recorded because a sweep whose output is quietly
dropped is a sweep nobody will run twice.

### Backend — three names with no reference anywhere

| Name | File | Why it is dead |
|---|---|---|
| `require_active_role` | `backend/app/repositories/memberships_repository.py:10` | superseded by `get_active_membership` / `require_membership_role` in `deps.py`. It is also the **only** consumer of `Role` in that file — see the note below |
| `WithdrawAccessRequest` | `backend/app/domain/schemas.py:253` | an empty `StrictModel` (`pass`). `withdraw_access_request` takes no body |
| `ACCESS_COOKIE`, `REFRESH_COOKIE`, `CSRF_COOKIE` | `backend/app/core/web_session.py:23-25` | superseded by `cookie_name("access"\|"refresh"\|"csrf")`, which computes the same names and is what every call site uses |

**`require_active_role` is worth a second look rather than a straight delete.**
[Issue 2](README.md#2-rolespy-documents-an-rbac-model-the-code-no-longer-uses) kept
`Role` in `roles.py` on the grounds that this file imports it. If this function
goes, that reason goes with it, and `Role` should be re-examined at the same time.
The three cookie constants are the safer kind of dead: two names for one value,
where the unused one is the one a reader would reach for first.

### Frontend — two modules and eight exports nothing imports

| Kind | What |
|---|---|
| module | `frontend/src/features/amenities/components/AmenityTabPlaceholder.jsx` |
| module | `frontend/src/pages/Signup/SignupPage.jsx` |
| exports | `validateCreateBooking`, `createResidentAmenityBooking`, `formatAmenityOperatingHours`, `SESSION_STATUS`, `createEmptyAdminProfile`, `normalizePhoneNumber`, `sanitizePhoneInput`, `isValidMobileNumber` |

`utils/phone.js` is the notable one: **all three of its exports are unused**, which
is the shape of a module left behind by the phone/OTP design the project no longer
uses — the same drift [issue 7](README.md#7-design-docs-outside-apimd-still-describe-phonesms-otp)
records in the documents. `SignupPage.jsx` is likewise a route that
`App.jsx` no longer mounts.

The export list is produced by a **word search**, not an import graph, so a name
reached through a barrel file or `import * as` would not appear. It under-reports
on purpose; every entry above is real.

### `graphify-out/` — 57 tracked files, 2.6 MB

A code-graph tool's output directory, committed in `added google oAuth support`
and tracked since. It holds `graph.json`, `graph.html`, a `cache/` tree and a
`cost.json`. Nothing in the build, the tests or the documentation refers to it.

It is not harmful, and it is 2.6 MB every clone pays for, in a repository whose
next-largest generated artifact — `docs/openapi.yaml` — is deliberately committed
*because* it is reviewed. This one is not reviewed by anyone.

## Why it matters

None of this is a bug and none of it is urgent. Two reasons it is worth a file:

1. **Dead code is read as live.** `require_active_role` carries a docstring
   explaining why the caller-scoped client is intentional and how RLS makes it a
   second boundary. That is exactly the sort of thing someone will copy, believing
   it to be the house pattern, when the house pattern is `deps.py`.
2. **The sweep only stays useful if its output goes somewhere.** This is the same
   argument [issue 10](10-api-operations-with-no-frontend-consumer.md) makes about
   `frontend_api_sweep.py`: the numbers move in both directions, and a list nobody
   acts on decays into noise that the next reader learns to skip.

## How to confirm

```bash
cd backend && python scripts/dead_code_sweep.py
```

The script's docstring records what each section does and does not model,
including the standing blind spot: a name whose only caller is *itself* dead still
counts as live, so it is worth re-running after acting on the output.

For the tracked directory:

```bash
git ls-files graphify-out | wc -l
```

## Suggested fix

- **The three backend names**: delete, with `require_active_role` and `Role` looked
  at together. One commit, no behaviour change — every one has zero references.
- **The frontend modules and exports**: the amenity and auth owners' call. The
  three `phone.js` exports should go with whatever closes issue 7.
- **`graphify-out/`**: `git rm -r --cached graphify-out` and a `.gitignore` line,
  if the tool is still in use; delete outright if it is not. Ask before doing
  either — it is not this workstream's to remove, and the history keeps it either
  way.
