import { AUTH_PROVIDER } from './config';
import { getSupabaseClient } from './supabaseClient';

function callbackUrl() {
  return new URL('/auth/callback', window.location.origin).toString();
}

export const authProviders = Object.freeze({
  [AUTH_PROVIDER.GOOGLE]: {
    async start() {
      const { error } = await getSupabaseClient().auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: callbackUrl() },
      });
      if (error) throw error;
    },
    async link() {
      const { error } = await getSupabaseClient().auth.linkIdentity({
        provider: 'google',
        options: { redirectTo: callbackUrl() },
      });
      if (error) throw error;
    },
  },
  [AUTH_PROVIDER.OTP]: {
    async request({ phone }) {
      const { error } = await getSupabaseClient().auth.signInWithOtp({
        phone,
        options: { shouldCreateUser: false },
      });
      if (error) throw error;
    },
    async verify({ phone, token }) {
      const { data, error } = await getSupabaseClient().auth.verifyOtp({
        phone,
        token,
        type: 'sms',
      });
      if (error) throw error;
      return data.session;
    },
  },
});
