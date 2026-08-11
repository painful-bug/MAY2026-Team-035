import { useParams } from 'react-router-dom';

import { homeRouteFor } from '../../routes/authRoutes';
import { useApp } from '../../store/useApp';

/**
 * Where the hiring screens are mounted for *this* caller, and what they may do.
 *
 * **The hiring surface has three doors and one implementation.** The endpoints
 * behind it accept `admin` or `manager` — `require_admin_or_manager` at the
 * router, `can_manage_department` inside every RPC — and until 2026-08-11 only
 * the admin portal had screens. A department manager and a security-department
 * manager both hold `membership_role = 'manager'`, both pass both guards, and
 * both landed on a portal with no way in. That is
 * `docs/potential issues/14`, and this hook is how it closes.
 *
 * ## Why a hook and not a `basePath` prop
 *
 * A prop would have to be passed correctly at every mount, and the failure when
 * it is not is a link that renders fine and 403s on click — the exact bug being
 * fixed, reintroduced by the fix. `homeRouteFor` already answers "where does
 * this person live" from `portal`, which the **backend** computes; deriving the
 * base from it means the screens cannot disagree with the router about who is
 * looking at them.
 *
 * ## Why `accessRole` and not `role`
 *
 * `role` is the display label and it conflates two people. A security
 * department's *manager* holds `membership_role = 'manager'` and is labelled
 * `SecurityManager`; so is a **senior guard**, who holds `membership_role =
 * 'security'` with a manager-or-supervisor roster rank (`_portal_for`,
 * `auth_service.py`). They share a portal and they do not share this
 * permission: `require_admin_or_manager` refuses the guard. `accessRole` is the
 * uppercased membership role, so `canHire` is that guard spelled in the
 * browser — and a Hiring tab shown to a senior guard would be a tab that 403s.
 *
 * ## The department id stays in the URL for everybody
 *
 * A manager could have had `/manager/hiring` with the id implied by their
 * session. Keeping the admin's shape — `{base}/departments/:departmentId/…` —
 * means one set of links, one component, and no branch that only one portal
 * exercises. Typing somebody else's department id is not a way in:
 * `can_manage_department` refuses it in Postgres, which is the posture
 * `department_hiring.py` states outright — *an id arriving in a URL is never an
 * authorization decision*.
 */
export function usePortalScope() {
  const { currentUser } = useApp();
  const params = useParams();

  return {
    /** `/admin`, `/manager` or `/security-manager`. Never a trailing slash. */
    base: homeRouteFor(currentUser),
    /**
     * The department these screens are about: the URL's, else the one the
     * caller's own membership names. The fallback is what lets a manager's nav
     * item be built before any route has supplied an id.
     */
    departmentId: params.departmentId || currentUser?.departmentId || null,
    /** True when the API would accept this caller's hiring calls. */
    canHire:
      currentUser?.accessRole === 'ADMIN' || currentUser?.accessRole === 'MANAGER',
  };
}
