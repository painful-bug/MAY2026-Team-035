import { create } from 'zustand';
import { useAppStore } from './appStore';
import {
  applicationUser, getApplicationSession, logoutSession, redeemPreparedInvitation,
} from '../lib/auth/authService';
import { queryClient } from '../lib/api/queryClient';

export const AUTH_FLOW_STATE = Object.freeze({
  IDLE: 'idle', INITIALIZING: 'initializing', REDIRECTING: 'redirecting', AUTHENTICATED: 'authenticated', ERROR: 'error',
});

export const SESSION_STATUS = Object.freeze({
  LOADING: 'loading', ANONYMOUS: 'anonymous', ONBOARDING: 'onboarding', MEMBER: 'member', ERROR: 'error',
});

const initialState = { currentUser: null, sessionContext: null, sessionStatus: SESSION_STATUS.LOADING, authFlowState: AUTH_FLOW_STATE.IDLE, authError: '', isAuthReady: false, authGeneration: 0 };
let bootstrapPromise = null;
const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('homebandhu-auth') : null;

function sessionState(context) {
  return {
    sessionContext: context,
    currentUser: applicationUser(context),
    sessionStatus: context.membership ? SESSION_STATUS.MEMBER : SESSION_STATUS.ONBOARDING,
    authFlowState: AUTH_FLOW_STATE.AUTHENTICATED,
    isAuthReady: true,
  };
}

function startOAuth(provider, next = '/auth/callback', remember = false) {
  // `remember` is only sent when it was asked for: the backend defaults to a
  // browser-session refresh cookie, which is the safe answer on a shared device.
  const rememberParam = remember ? '&remember=true' : '';
  window.location.assign(`/api/v1/auth/oauth/${encodeURIComponent(provider)}/start?next=${encodeURIComponent(next)}${rememberParam}`);
}

export const useAuthStore = create((set, get) => ({
  ...initialState,

  initializeAuth: async () => {
    if (bootstrapPromise) return bootstrapPromise;
    const generation = get().authGeneration;
    set({ authFlowState: AUTH_FLOW_STATE.INITIALIZING, isAuthReady: false, authError: '' });
    bootstrapPromise = (async () => {
      try {
        const context = await getApplicationSession();
        if (get().authGeneration === generation) set(sessionState(context));
      } catch {
        if (get().authGeneration === generation) set({ ...initialState, authGeneration: generation, sessionStatus: SESSION_STATUS.ANONYMOUS, isAuthReady: true });
      } finally { bootstrapPromise = null; }
    })();
    return bootstrapPromise;
  },

  beginOAuth: (provider, next, { remember = false } = {}) => {
    set({ authFlowState: AUTH_FLOW_STATE.REDIRECTING, authError: '' });
    startOAuth(provider, next, remember);
  },
  beginGoogleSignIn: (next, options) => get().beginOAuth('google', next, options),

  completeExternalLogin: async () => {
    const generation = get().authGeneration;
    try {
      const context = await getApplicationSession();
      if (get().authGeneration !== generation) return { success: false, message: 'Sign-in was superseded.' };
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
    // Clear the in-memory identity first so protected data subscriptions stop
    // before a slow network request can keep the previous session alive.
    const nextGeneration = get().authGeneration + 1;
    queryClient.clear();
    set({ ...initialState, authGeneration: nextGeneration, sessionStatus: SESSION_STATUS.ANONYMOUS, isAuthReady: true });
    channel?.postMessage({ type: 'logout' });
    useAppStore.getState().showToast('Logged out successfully', 'info');
    try {
      await logoutSession();
    } catch {
      // The browser is already locally signed out. A later request cannot use
      // the protected UI, and the server's cookie deletion is best effort.
    }
  },
}));

channel?.addEventListener('message', (event) => {
  if (event.data?.type !== 'logout') return;
  const state = useAuthStore.getState();
  queryClient.clear();
  useAuthStore.setState({ ...initialState, authGeneration: state.authGeneration + 1, sessionStatus: SESSION_STATUS.ANONYMOUS, isAuthReady: true });
});
