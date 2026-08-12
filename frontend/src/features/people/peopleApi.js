import { api } from '../../lib/api/client';

// The one people-write left in `people.py`: promoting an existing member.
//
// Same shape as the other feature api modules -- no state, no caching, no
// error translation. react-query owns all three.

export const peopleApi = {
  /**
   * Give an existing community member the `admin` role.
   *
   * **Promotes, does not invite.** The email must already belong to an active
   * member of the caller's community -- a 404 means "invite them first, then
   * promote". `name`, `phone`, `tower` and `flat` are accepted for the form's
   * sake but ignored by the server: a promotion must not rewrite the member's
   * profile or move them to a different flat.
   */
  promoteAdmin: (payload) =>
    api('/admins', { method: 'POST', body: JSON.stringify(payload) }),
};
