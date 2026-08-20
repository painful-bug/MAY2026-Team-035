import { api, API_TIMEOUTS, prepareAnonymousCsrf } from '../api/client';

const ROLE_LABELS = Object.freeze({
  ADMIN: 'Admin', MANAGER: 'Manager', WORKER: 'Worker', SECURITY: 'Security', RESIDENT: 'Resident',
});

export async function getApplicationSession() {
  return api('/auth/session');
}

export async function getAuthMethods(options = {}) {
  // This endpoint is public. It must not wait for a stale-session refresh.
  return api('/auth/methods', options, { retry: false, timeoutMs: API_TIMEOUTS.authMethods });
}

export async function logoutSession() {
  return api('/auth/logout', { method: 'POST' }, {
    retry: false,
    timeoutMs: API_TIMEOUTS.logout,
  });
}

export async function signUpWithPassword(payload) {
  await prepareAnonymousCsrf();
  return api('/auth/password/sign-up', { method: 'POST', body: JSON.stringify(payload) }, { retry: false });
}

export async function signInWithPassword(payload) {
  await prepareAnonymousCsrf();
  return api('/auth/password/sign-in', { method: 'POST', body: JSON.stringify(payload) }, { retry: false });
}

export async function verifyEmailToken(token_hash, verification_type = 'email') {
  await prepareAnonymousCsrf();
  return api('/auth/email/verify', { method: 'POST', body: JSON.stringify({ token_hash, verification_type }) }, { retry: false });
}

export async function resendEmailConfirmation(email, intent = null) {
  await prepareAnonymousCsrf();
  return api('/auth/email/resend', { method: 'POST', body: JSON.stringify({ email, intent }) }, { retry: false });
}

export async function requestPasswordReset(email) {
  await prepareAnonymousCsrf();
  return api('/auth/password/reset/request', { method: 'POST', body: JSON.stringify({ email }) }, { retry: false });
}

export async function verifyPasswordReset(token_hash) {
  await prepareAnonymousCsrf();
  return api('/auth/password/reset/verify', { method: 'POST', body: JSON.stringify({ token_hash }) }, { retry: false });
}

export async function completePasswordReset(password) {
  return api('/auth/password/reset/complete', { method: 'POST', body: JSON.stringify({ password }) }, { retry: false });
}

export async function prepareInvitation({ token, code }) {
  return api('/invitations/prepare', { method: 'POST', body: JSON.stringify({ token, code }) });
}

export async function redeemPreparedInvitation() {
  return api('/invitations/redeem', { method: 'POST', body: JSON.stringify({}) });
}

export function applicationUser(context) {
  const { identity, membership } = context;
  if (!membership) return null;
  const accessRole = String(membership.role || '').toUpperCase();
  // The portal wins over the membership role, and only ever narrows it. A
  // security department's manager holds `role = 'manager'`, and four screens
  // (Header, SecurityLayout, SecurityDashboard and the /security-manager route
  // guard) branch on the label `SecurityManager` — a value nothing had ever
  // produced, which is why that whole portal was unreachable.
  const role = context.portal === 'security-manager'
    ? 'SecurityManager'
    : ROLE_LABELS[accessRole] || 'Resident';
  return {
    id: identity.id, name: identity.full_name || identity.email || 'HomeBandhu member',
    email: identity.email || '', phone: identity.phone || '', role, accessRole,
    communityId: membership.community_id, apartmentId: membership.unit_id,
    // `membership.unit` carries the human-readable residency labels the header
    // chip renders. `tower` is null for standalone homes (units without a
    // building) — a community is apartments XOR standalone homes.
    flat: membership.unit?.unit_code ?? '—',
    tower: membership.unit?.building_name ?? null,
    unitType: membership.unit?.unit_type ?? null,
    buildingType: membership.unit?.building_type ?? null,
    status: 'Active',
    // Which department this person runs. `GET /auth/session` has always carried
    // it and nothing copied it across, which was harmless while no screen was
    // scoped to a department — the manager portal is the first, and it has no
    // other way to know: `GET /departments` is admin-only, so a manager cannot
    // look themselves up.
    departmentId: membership.department_id || null,
    portal: context.portal || null,
  };
}

// `homeRouteFor` used to live here and is now the single resolver in
// `routes/authRoutes.js`, next to the constants it returns. See the comment
// there for what the two functions were and why one of them was always wrong.
