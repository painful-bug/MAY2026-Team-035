import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../lib/api/client';

const { getApplicationSession } = vi.hoisted(() => ({
  getApplicationSession: vi.fn(),
}));

vi.mock('../lib/auth/authService', () => ({
  applicationUser: (context) => ({ id: context.identity.id }),
  getApplicationSession,
  logoutSession: vi.fn(),
  redeemPreparedInvitation: vi.fn(),
}));

import { SESSION_STATUS, useAuthStore } from './authStore';

const CONTEXT = { identity: { id: 'member-1' }, membership: { role: 'worker' } };

describe('session restoration', () => {
  beforeEach(() => {
    getApplicationSession.mockReset();
    useAuthStore.setState({
      currentUser: null, sessionContext: null, sessionStatus: SESSION_STATUS.LOADING,
      authFlowState: 'idle', authError: '', isAuthReady: false, authGeneration: 0,
    });
  });

  it('keeps a successful login when an earlier anonymous bootstrap finishes late', async () => {
    let rejectBootstrap;
    const bootstrap = new Promise((_, reject) => { rejectBootstrap = reject; });
    getApplicationSession.mockReturnValueOnce(bootstrap).mockResolvedValueOnce(CONTEXT);

    const restoring = useAuthStore.getState().initializeAuth();
    await expect(useAuthStore.getState().completeExternalLogin()).resolves.toMatchObject({ success: true });
    rejectBootstrap(new ApiError({ status: 401, code: 'authentication_error', message: 'Invalid authentication token.' }));
    await restoring;

    expect(useAuthStore.getState()).toMatchObject({
      sessionContext: CONTEXT, sessionStatus: SESSION_STATUS.MEMBER, isAuthReady: true,
    });
  });
});
