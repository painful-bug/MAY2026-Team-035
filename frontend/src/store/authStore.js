import { create } from 'zustand';
import { useAppStore } from './appStore';
import {
  applicationUser, getApplicationSession, logoutSession, redeemPreparedInvitation,
} from '../lib/auth/authService';

export const AUTH_FLOW_STATE = Object.freeze({
  IDLE: 'idle', INITIALIZING: 'initializing', REDIRECTING: 'redirecting', AUTHENTICATED: 'authenticated', ERROR: 'error',
});

export const SESSION_STATUS = Object.freeze({
  LOADING: 'loading', ANONYMOUS: 'anonymous', ONBOARDING: 'onboarding', MEMBER: 'member', ERROR: 'error',
});

const initialState = { currentUser: null, sessionContext: null, sessionStatus: SESSION_STATUS.LOADING, authFlowState: AUTH_FLOW_STATE.IDLE, authError: '', isAuthReady: false };

function sessionState(context) {
  return {
    sessionContext: context,
    currentUser: applicationUser(context),
    sessionStatus: context.membership ? SESSION_STATUS.MEMBER : SESSION_STATUS.ONBOARDING,
    authFlowState: AUTH_FLOW_STATE.AUTHENTICATED,
    isAuthReady: true,
  };
}

function startGoogle(next = '/auth/callback') {
  window.location.assign(`/api/v1/auth/google/start?next=${encodeURIComponent(next)}`);
}

export const useAuthStore = create((set) => ({
  ...initialState,

  initializeAuth: async () => {
    set({ authFlowState: AUTH_FLOW_STATE.INITIALIZING, isAuthReady: false, authError: '' });
    try {
      const context = await getApplicationSession();
      set(sessionState(context));
    } catch {
      set({ ...initialState, sessionStatus: SESSION_STATUS.ANONYMOUS, isAuthReady: true });
    }
  },

  beginGoogleSignIn: (next) => {
    set({ authFlowState: AUTH_FLOW_STATE.REDIRECTING, authError: '' });
    startGoogle(next);
  },

  completeExternalLogin: async () => {
    try {
      const context = await getApplicationSession();
      set(sessionState(context));
      return { success: true, user: applicationUser(context), context, onboardingEligible: context.onboarding_eligible };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to complete Google sign-in.';
      set({ ...initialState, sessionStatus: SESSION_STATUS.ERROR, authFlowState: AUTH_FLOW_STATE.ERROR, authError: message, isAuthReady: true });
      return { success: false, message };
    }
  },

  redeemInvite: async () => {
    try {
      await redeemPreparedInvitation();
      return useAuthStore.getState().completeExternalLogin();
    } catch (error) {
      return { success: false, message: error instanceof Error ? error.message : 'Unable to redeem this invitation.' };
    }
  },

  refreshSession: async () => {
    const context = await getApplicationSession();
    set(sessionState(context));
    return context;
  },

  logout: async () => {
    try { await logoutSession(); } finally {
      set({ ...initialState, sessionStatus: SESSION_STATUS.ANONYMOUS, isAuthReady: true });
      useAppStore.getState().showToast('Logged out successfully', 'info');
    }
  },
}));
