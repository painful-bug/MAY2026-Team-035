// Pure invite-redemption logic — no store, no React, so it's trivially testable
// (see selfcheck.mjs). The slice just wraps this and commits the result.

export const inviteError = {
  invalid: 'This invite link is not valid.',
  used: 'This invite has already been used.',
  expired: 'This invite link has expired. Ask the admin for a new one.',
};

// state: { users, invitations }; opts: { phone?, now? }
// -> { ok:true, users, invitations, user } | { ok:false, reason }
export function applyRedeem(state, token, opts = {}) {
  const now = opts.now ?? Date.now();
  const invite = state.invitations.find((i) => i.token === token);

  if (!invite) return { ok: false, reason: 'invalid' };
  if (invite.used) return { ok: false, reason: 'used' };
  if (invite.expiresAt && now > invite.expiresAt) return { ok: false, reason: 'expired' };

  // "One number registered => all numbers of the flat registered": activate
  // every user of the apartment, not just the one who clicked.
  const users = state.users.map((u) =>
    u.apartmentId === invite.apartmentId ? { ...u, status: 'Active' } : u
  );

  const invitations = state.invitations.map((i) =>
    i.token === token ? { ...i, used: true, usedAt: now } : i
  );

  const flatUsers = users.filter((u) => u.apartmentId === invite.apartmentId);
  const clean = (p) => (p || '').replace(/\s+/g, '');
  const user =
    (opts.phone && flatUsers.find((u) => clean(u.phone) === clean(opts.phone))) ||
    flatUsers[0] ||
    null;

  return { ok: true, users, invitations, user };
}
