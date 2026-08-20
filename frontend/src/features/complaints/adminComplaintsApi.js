import { api } from '../../lib/api/client';
import { getDashboardSnapshot } from '../../lib/dashboard/dashboardApi';

// The administrator raising a complaint from their own portal.
//
// Same shape as `routingApi.js` and `features/departments`: no state, no
// caching, no error translation — react-query owns all three.
//
// **Why a separate endpoint from `POST /complaints`.** That one raises the
// caller's own complaint and is guarded by the resident capability. An admin
// raises in two modes neither of which is "mine": on behalf of a resident (the
// complaint belongs to that resident and shows on *their* portal, with the
// admin recorded as the actor of the `raised` event), or attached to no
// residential unit at all — an amenity or a common area — which is owned by the
// admin's membership and stays on the admin portal.
//
// Which of the two is decided by exactly one field, `forMembershipId`: present
// means on-behalf, absent means community/amenity. The browser does not label
// the mode; it names the resident or it does not.

const post = (path, body = {}) => api(path, { method: 'POST', body: JSON.stringify(body) });

export const adminComplaintsApi = {
  /**
   * `{ title, description?, category, priority?, location?, departmentId?,
   *    skillId?, forMembershipId? }` → `201 { id, message }`.
   *
   * `priority` is the stored vocabulary (`low` | `medium` | `high`), not the
   * resident form's `urgency` (`Low` | `Medium` | `High`). The admin surfaces
   * already speak the lowercase one — the triage queue renders
   * `complaint.priority` against lowercase keys — and this endpoint is an admin
   * surface, so it does not import the resident translation.
   *
   * `category` is sent as the chosen trade's name even though `skillId` is also
   * sent. The database snapshots the skill's current name into `category`
   * itself, so the two agree by construction; sending it means the request is
   * still well-formed if the schema requires the field, and costs nothing if it
   * does not.
   */
  raise: (payload) => post('/complaints/admin-raise', payload),

  /**
   * Who the "on behalf of" picker may name.
   *
   * Read from `GET /dashboard/snapshot` because there is no `GET /residents` —
   * §6 of docs/API.md says so, and `amenitiesApi.bookableResidents` sources its
   * own picker the same way. The snapshot is ADMIN/MANAGER-guarded, which is
   * where this picker lives.
   *
   * **`membershipId`, not `id`.** The snapshot's `id` is the PROFILE id and
   * `forMembershipId` is the community membership id; sending the profile id
   * names nobody.
   *
   * **Filtered on having a flat, not on `role === 'Resident'`.** Resident-ness
   * is an active `unit_residencies` row, never a role implication — an admin
   * with a flat is a resident too, and the snapshot's `flat` is derived from
   * exactly that residency (`'—'` when there is none). Filtering on the role
   * label would have hidden every admin and every department manager who lives
   * here, which is the population most likely to be asked "raise this for me".
   */
  residentOptions: async () => {
    const snapshot = await getDashboardSnapshot();
    return (snapshot.users || [])
      .filter(
        (user) =>
          user.status === 'Active' &&
          user.membershipId &&
          user.flat &&
          user.flat !== '—'
      )
      .map((user) => ({
        membershipId: user.membershipId,
        name: user.name,
        flat: user.flat,
        tower: user.tower && user.tower !== '—' ? user.tower : '',
        role: user.role,
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  },
};
