import { useQuery } from '@tanstack/react-query';

import { departmentsApi } from '../../features/departments/departmentsApi';
import { hiringApi } from '../../features/hiring/hiringApi';
import { useApp } from '../../store/useApp';

/**
 * The department this manager runs, and the id every screen here needs.
 *
 * **The id comes from the session, not from a list.** `GET /departments` is
 * admin-only, so a manager cannot look themselves up — the only thing that
 * knows which department they run is `membership.department_id`, which
 * `GET /auth/session` has always carried and which `applicationUser` now
 * copies onto the user.
 *
 * `departmentId` being null is a real state and not an error: a `manager`
 * membership with no department is legal in the schema, and
 * `can_manage_department` treats it as "manages any" — which is a decision for
 * the admin portal, not a screen to build here. Every page below renders a
 * plain explanation rather than an empty dashboard.
 */
export function useManagerDepartment() {
  const { currentUser } = useApp();
  const departmentId = currentUser?.departmentId || null;

  const department = useQuery({
    queryKey: ['departments', departmentId, 'detail'],
    // `GET /departments/{id}` was widened to admins *and* the department's own
    // manager for exactly this call. It was also the only department operation
    // with no frontend caller at all.
    queryFn: () => hiringApi.departmentDetail(departmentId),
    enabled: Boolean(departmentId),
  });

  const invitations = useQuery({
    queryKey: ['departments', departmentId, 'staff-invitations'],
    queryFn: () => departmentsApi.staffInvitations(departmentId, { status: 'pending' }),
    enabled: Boolean(departmentId),
  });

  return {
    departmentId,
    department: department.data || null,
    roster: (department.data?.staff ?? []).filter(
      (member) => member.status !== 'inactive'
    ),
    pendingInvitations: invitations.data ?? [],
    isLoading: department.isLoading,
    error: department.error,
  };
}
