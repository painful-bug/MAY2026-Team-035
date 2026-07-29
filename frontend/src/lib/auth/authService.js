import { api } from '../api/client';

const ROLE_LABELS = Object.freeze({
  ADMIN: 'Admin', MANAGER: 'Manager', WORKER: 'Worker', SECURITY: 'Security', RESIDENT: 'Resident',
});

export async function getApplicationSession() {
  return api('/auth/session');
}

export async function getAuthMethods() {
  return api('/auth/methods');
}

export async function logoutSession() {
  return api('/auth/logout', { method: 'POST' });
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
  const role = ROLE_LABELS[accessRole] || 'Resident';
  return {
    id: identity.id, name: identity.full_name || identity.email || 'HomeBandhu member',
    email: identity.email || '', phone: identity.phone || '', role, accessRole,
    communityId: membership.community_id, apartmentId: membership.unit_id, flat: '—', tower: '—', status: 'Active',
    portal: context.portal || null,
  };
}

export function homeRouteFor(contextOrUser) {
  const context = contextOrUser?.identity ? contextOrUser : null;
  if (context) {
    if (!context.membership && context.onboarding_eligible) return '/get-started';
    const role = String(context.membership?.role || '').toLowerCase();
    if (role === 'admin') return '/admin';
    if (context.portal === 'security-manager') return '/security-manager';
    if (role === 'security') return '/security';
    if (role === 'resident') return '/resident';
    return '/account';
  }
  if (contextOrUser?.accessRole === 'ADMIN') return '/admin';
  if (contextOrUser?.portal === 'security-manager') return '/security-manager';
  if (contextOrUser?.accessRole === 'SECURITY') return '/security';
  if (contextOrUser?.accessRole === 'RESIDENT') return '/resident';
  return '/account';
}
