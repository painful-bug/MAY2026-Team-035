import { AUTH_PROVIDER } from './config';
import { authProviders } from './providers';
import { getSupabaseClient } from './supabaseClient';

const ROLE_LABELS = Object.freeze({
  ADMIN: 'Admin',
  MANAGER: 'Manager',
  WORKER: 'Worker',
  SECURITY: 'Security',
  RESIDENT: 'Resident',
});

function requireProvider(provider) {
  const implementation = authProviders[provider];
  if (!implementation) throw new Error(`Unsupported authentication provider: ${provider}`);
  return implementation;
}

export async function beginAuthentication(provider) {
  const implementation = requireProvider(provider);
  if (!implementation.start) {
    throw new Error('This authentication method requires a phone number.');
  }
  await implementation.start();
}

export async function requestOtp(phone) {
  await requireProvider(AUTH_PROVIDER.OTP).request({ phone });
}

export async function verifyOtp(phone, token) {
  return requireProvider(AUTH_PROVIDER.OTP).verify({ phone, token });
}

export async function linkGoogleIdentity() {
  await requireProvider(AUTH_PROVIDER.GOOGLE).link();
}

export async function redeemResidentInvite(phone, token) {
  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '');
  const response = await fetch(`${apiBaseUrl}/auth/redeem`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, token }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || body.detail || 'This invite is not valid.');

  const { data, error } = await getSupabaseClient().auth.setSession({
    access_token: body.access_token,
    refresh_token: body.refresh_token,
  });
  if (error || !data.session) throw error || new Error('Invite was accepted but no session was returned.');
  return data.session;
}

export async function getSession() {
  const { data, error } = await getSupabaseClient().auth.getSession();
  if (error) throw error;
  return data.session;
}

export async function signOut() {
  const { error } = await getSupabaseClient().auth.signOut();
  if (error) throw error;
}

export function onAuthStateChange(listener) {
  return getSupabaseClient().auth.onAuthStateChange((_event, session) => listener(session));
}

export async function resolveApplicationUser(session) {
  const supabase = getSupabaseClient();
  const [profileResult, membershipResult] = await Promise.all([
    supabase
      .from('profiles')
      .select('id, full_name, phone_e164, display_email, is_active')
      .eq('id', session.user.id)
      .single(),
    supabase
      .from('community_memberships')
      .select('role, community_id, is_default_community')
      .eq('profile_id', session.user.id)
      .eq('status', 'active')
      .is('ended_at', null)
      .order('is_default_community', { ascending: false })
      .limit(1)
      .maybeSingle(),
  ]);

  if (profileResult.error || !profileResult.data?.is_active) {
    throw new Error('Your account is not active. Please contact your community administrator.');
  }
  if (membershipResult.error || !membershipResult.data) {
    throw new Error('Your account does not have an active community role. Please contact your administrator.');
  }

  const membership = membershipResult.data;
  const accessRole = String(membership.role).toUpperCase();
  const role = ROLE_LABELS[accessRole] || 'Resident';
  const metadata = session.user.user_metadata || {};

  return {
    id: session.user.id,
    name: profileResult.data.full_name || metadata.full_name || session.user.email || 'HomeBandhu member',
    email: profileResult.data.display_email || session.user.email || '',
    phone: profileResult.data.phone_e164 || session.user.phone || '',
    role,
    accessRole,
    communityId: membership.community_id,
    flat: '—',
    tower: '—',
    apartmentId: null,
    status: 'Active',
  };
}

export function homeRouteFor(user) {
  return user.accessRole === 'ADMIN' ? '/admin' : '/resident';
}
