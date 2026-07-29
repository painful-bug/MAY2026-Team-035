import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { useAppStore } from './appStore';
import {
  beginAuthentication,
  getSession,
  linkGoogleIdentity,
  onAuthStateChange,
  redeemResidentInvite,
  requestOtp,
  resolveApplicationUser,
  signOut,
  verifyOtp,
} from '../lib/auth/authService';
import { isSupabaseAuthConfigured } from '../lib/auth/supabaseClient';
import {
  isValidMobileNumber,
  normalizePhoneNumber,
  sanitizePhoneInput,
} from '../utils/phone';
import { findSecurityCommunityAccount } from '../lib/securityAccounts';

export const ADMIN_REGISTRATION_STATUS = Object.freeze({
  UNKNOWN: 'unknown',
  REGISTERED: 'registered',
  NEW_ADMIN: 'new_admin',
});

export const AUTH_FLOW_STATE = Object.freeze({
  IDLE: 'idle',
  INITIALIZING: 'initializing',
  REDIRECTING: 'redirecting',
  OTP_REQUIRED: 'otp_required',
  OTP_SUBMITTING: 'otp_submitting',
  // Retained while the separate association-onboarding flow is migrated to the
  // backend. It is no longer entered by the login screen.
  REGISTRATION_REQUIRED: 'registration_required',
  AUTHENTICATED: 'authenticated',
  ERROR: 'error',
});

const initialAuthState = {
  currentUser: null,
  currentPhone: '',
  registrationStatus: ADMIN_REGISTRATION_STATUS.UNKNOWN,
  authFlowState: AUTH_FLOW_STATE.IDLE,
  authProvider: null,
  authError: '',
  isAuthReady: false,
};

let subscription;

function messageFrom(error, fallback) {
  const message = error instanceof Error && error.message ? error.message : fallback;
  if (/unsupported provider.*not enabled/i.test(message)) {
    return 'Google sign-in is not enabled for this Supabase project yet. Use phone OTP or ask an administrator to enable the Google provider.';
  }
  return message;
}

async function hydrateSession(set, session) {
  if (!session) {
    set({
      currentUser: null,
      authProvider: null,
      authFlowState: AUTH_FLOW_STATE.IDLE,
      authError: '',
      isAuthReady: true,
    });
    return { success: true, user: null };
  }

  set({ authFlowState: AUTH_FLOW_STATE.INITIALIZING, authError: '' });
  try {
    const user = await resolveApplicationUser(session);
    set({
      currentUser: user,
      authFlowState: AUTH_FLOW_STATE.AUTHENTICATED,
      authError: '',
      isAuthReady: true,
    });
    return { success: true, user };
  } catch (error) {
    const message = messageFrom(error, 'Unable to load your HomeBandhu access.');
    set({
      currentUser: null,
      authFlowState: AUTH_FLOW_STATE.ERROR,
      authError: message,
      isAuthReady: true,
    });
    return { success: false, message };
  }
}

// The auth store never manufactures a user. Every authenticated UI identity is
// derived from a Supabase session plus an active community membership.
export const useAuthStore = create(
  persist(
    (set, get) => ({
      ...initialAuthState,

      // Compatibility for the still-local resident/security demonstration
      // routes. Production sign-in always hydrates this identity from Supabase.
      setCurrentUser: (currentUser) =>
        set({
          currentUser,
          authFlowState: currentUser
            ? AUTH_FLOW_STATE.AUTHENTICATED
            : AUTH_FLOW_STATE.IDLE,
          isAuthReady: true,
        }),

      initializeAuth: async () => {
        if (!isSupabaseAuthConfigured()) {
          set({
            currentUser: null,
            authFlowState: AUTH_FLOW_STATE.ERROR,
            authError: 'Authentication is not configured for this environment.',
            isAuthReady: true,
          });
          return;
        }

        set({ authFlowState: AUTH_FLOW_STATE.INITIALIZING, isAuthReady: false });
        try {
          await hydrateSession(set, await getSession());
        } catch (error) {
          set({
            currentUser: null,
            authFlowState: AUTH_FLOW_STATE.ERROR,
            authError: messageFrom(error, 'Unable to restore your session.'),
            isAuthReady: true,
          });
        }

        if (!subscription) {
          subscription = onAuthStateChange((session) => {
            void hydrateSession(set, session);
          }).data.subscription;
        }
      },

      setCurrentPhone: (phone) =>
        set({
          currentPhone: sanitizePhoneInput(phone),
          authError: '',
          registrationStatus: ADMIN_REGISTRATION_STATUS.UNKNOWN,
        }),

      beginProviderSignIn: async (provider) => {
        if (!isSupabaseAuthConfigured()) {
          return { success: false, message: 'Authentication is not configured for this environment.' };
        }

        set({ authProvider: provider, authFlowState: AUTH_FLOW_STATE.REDIRECTING, authError: '' });
        try {
          await beginAuthentication(provider);
          return { success: true };
        } catch (error) {
          const message = messageFrom(error, 'Unable to start sign in.');
          set({ authFlowState: AUTH_FLOW_STATE.IDLE, authError: message });
          return { success: false, message };
        }
      },

      requestPhoneOtp: async () => {
        const phone = normalizePhoneNumber(get().currentPhone);
        if (!isValidMobileNumber(phone)) {
          return { success: false, message: 'Please enter a valid 10-digit mobile number.' };
        }

        set({ authProvider: 'otp', authFlowState: AUTH_FLOW_STATE.OTP_SUBMITTING, authError: '' });
        try {
          await requestOtp(`+91${phone}`);
          set({ currentPhone: phone, authFlowState: AUTH_FLOW_STATE.OTP_REQUIRED });
          return { success: true };
        } catch (error) {
          const message = messageFrom(error, 'Unable to send the OTP. Please try again.');
          set({ authFlowState: AUTH_FLOW_STATE.IDLE, authError: message });
          return { success: false, message };
        }
      },

      submitAdminOtp: async (otp) => {
        const phone = normalizePhoneNumber(get().currentPhone);
        if (!isValidMobileNumber(phone) || get().authFlowState !== AUTH_FLOW_STATE.OTP_REQUIRED) {
          return { success: false, message: 'Request a new OTP before submitting it.' };
        }

        set({ authFlowState: AUTH_FLOW_STATE.OTP_SUBMITTING, authError: '' });
        try {
          const session = await verifyOtp(`+91${phone}`, otp);
          if (!session) throw new Error('Invalid or expired OTP.');
          const result = await hydrateSession(set, session);
          if (result.success && result.user) {
            useAppStore.getState().showToast(`Welcome back, ${result.user.name}!`, 'success');
          }
          return result;
        } catch (error) {
          const message = messageFrom(error, 'Unable to verify the OTP. Please try again.');
          set({ authFlowState: AUTH_FLOW_STATE.OTP_REQUIRED, authError: message });
          return { success: false, message };
        }
      },

      completeExternalLogin: async () => {
        try {
          return await hydrateSession(set, await getSession());
        } catch (error) {
          const message = messageFrom(error, 'Unable to complete sign in.');
          set({ authFlowState: AUTH_FLOW_STATE.ERROR, authError: message, isAuthReady: true });
          return { success: false, message };
        }
      },

      linkGoogleIdentity: async () => {
        set({ authFlowState: AUTH_FLOW_STATE.REDIRECTING, authError: '' });
        try {
          await linkGoogleIdentity();
          return { success: true };
        } catch (error) {
          const message = messageFrom(error, 'Unable to link your Google account.');
          set({ authFlowState: AUTH_FLOW_STATE.AUTHENTICATED, authError: message });
          return { success: false, message };
        }
      },

      redeemInvite: async (token, phone) => {
        try {
          const session = await redeemResidentInvite(phone, token);
          return hydrateSession(set, session);
        } catch (error) {
          return { success: false, message: messageFrom(error, 'Unable to redeem this invite.') };
        }
      },

      resetAdminAuthentication: () =>
        set({
          currentPhone: '',
          registrationStatus: ADMIN_REGISTRATION_STATUS.UNKNOWN,
          authFlowState: AUTH_FLOW_STATE.IDLE,
          authProvider: null,
          authError: '',
        }),

      // The resident and security portals remain local demonstrations until
      // their corresponding backend authentication paths are migrated. Do not
      // use this action from the Google/OTP sign-in flow.
      login: (phone) => {
        const app = useAppStore.getState();
        const cleanPhone = normalizePhoneNumber(phone);
        const user =
          app.users.find(
            (candidate) =>
              normalizePhoneNumber(candidate.phone) === cleanPhone
          ) || findSecurityCommunityAccount(app.departments, cleanPhone);

        if (!user) {
          return {
            success: false,
            message: 'Invalid credentials. Phone number not registered.',
          };
        }
        if (user.status !== 'Active') {
          return {
            success: false,
            message: 'This account is inactive. Contact your society administrator.',
          };
        }

        set({
          currentUser: user,
          currentPhone: cleanPhone,
          registrationStatus:
            user.role === 'Admin'
              ? ADMIN_REGISTRATION_STATUS.REGISTERED
              : ADMIN_REGISTRATION_STATUS.UNKNOWN,
          authFlowState: AUTH_FLOW_STATE.AUTHENTICATED,
          authError: '',
          isAuthReady: true,
        });
        app.showToast(`Welcome back, ${user.name}!`, 'success');
        return { success: true, user };
      },

      logout: async () => {
        try {
          if (isSupabaseAuthConfigured()) await signOut();
        } finally {
          set({ ...initialAuthState, isAuthReady: true });
          useAppStore.getState().showToast('Logged out successfully', 'info');
        }
      },
    }),
    {
      name: 'homebandhu-auth',
      storage: createJSONStorage(() => sessionStorage),
      // Supabase owns session persistence. Keep no browser-created identity
      // around that could be mistaken for a valid server session.
      partialize: (state) => ({ currentPhone: state.currentPhone }),
    }
  )
);
