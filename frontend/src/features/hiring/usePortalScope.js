import { useParams } from 'react-router-dom';

import { homeRouteFor } from '../../routes/authRoutes';
import { useApp } from '../../store/useApp';

/**
 * Where the hiring screens are mounted for *this* caller, and what they may do.
 *
 * **The hiring surface has three doors and one implementation.** Until
 * 2026-08-11 only the admin portal had screens, while a department manager and
 * a security-department manager both passed every guard on the endpoints behind
 * it — and both landed on a portal with no way in. That is
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
 * ## What this hook deliberately does *not* answer
 *
 * It used to return a `canHire`, spelled `accessRole === 'ADMIN' || 'MANAGER'`
 * because that was `require_admin_or_manager` written in the browser. **There
 * is no longer a role that answers the question.** `can_hire_for_department`
 * gives hiring to the department's own active manager — by membership *or* by
 * roster rank, which for a security department means `membership_role =
 * 'security'` — and admits community admins as a fallback **only while it has
 * neither**. So the same admin may hire for one department and not the next one
 * down the list, and no property of the caller can say which.
 *
 * The department read answers it instead: `GET /departments/{id}` carries
 * `canHire`, computed by calling that exact function, so the screen and the RPC
 * cannot disagree. Nav items stay coarse — they decide who reaches the surface,
 * and the surface explains itself.
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
  };
}
