import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import {
  beforeEach, describe, expect, it, vi,
} from 'vitest';
import AuthEntryPage from './AuthEntryPage';

// "Remember me" is the one control on this card that decides whether the login
// page is here again next time, so the default matters as much as the wiring:
// unchecked, and `remember_me: false` on the wire.

const METHODS = {
  primary: 'google',
  methods: [
    { id: 'google', kind: 'redirect', label: 'Continue with Google', enabled: true },
    { id: 'email_password', kind: 'credentials', label: 'Continue with email', enabled: true },
  ],
};

const signInWithPassword = vi.fn(() => Promise.resolve({ message: 'Signed in.' }));
const beginOAuth = vi.fn();
const completeExternalLogin = vi.fn(() => Promise.resolve({ success: true, context: {} }));

vi.mock('../../lib/auth/authService', () => ({
  getAuthMethods: () => Promise.resolve(METHODS),
  signInWithPassword: (...args) => signInWithPassword(...args),
  signUpWithPassword: vi.fn(() => Promise.resolve({ message: 'Check your email.' })),
}));

vi.mock('../../lib/telemetry/serviceSignupTelemetry', () => ({
  recordServiceSignupEvent: vi.fn(),
}));

vi.mock('../../store/authStore', () => ({
  AUTH_FLOW_STATE: {
    IDLE: 'idle', INITIALIZING: 'initializing', REDIRECTING: 'redirecting', AUTHENTICATED: 'authenticated', ERROR: 'error',
  },
  useAuthStore: (selector) => selector({
    beginOAuth,
    completeExternalLogin,
    authFlowState: 'idle',
    sessionContext: null,
    isAuthReady: true,
    logout: vi.fn(),
  }),
}));

async function renderCard() {
  render(<MemoryRouter><AuthEntryPage /></MemoryRouter>);
  return waitFor(() => screen.getByRole('checkbox', { name: /remember me/i }));
}

async function fillCredentials(user) {
  await user.type(screen.getByPlaceholderText('Email'), 'resident@example.test');
  await user.type(screen.getByPlaceholderText('Password'), 'a-long-enough-password');
}

describe('AuthEntryPage remember me', () => {
  beforeEach(() => {
    signInWithPassword.mockClear();
    beginOAuth.mockClear();
  });

  it('offers one checkbox, unchecked, in sign-in mode', async () => {
    const checkbox = await renderCard();

    expect(screen.getAllByRole('checkbox')).toHaveLength(1);
    expect(checkbox).not.toBeChecked();
  });

  it('signs in without persistence unless it was asked for', async () => {
    const user = userEvent.setup();
    await renderCard();
    await fillCredentials(user);

    await user.click(screen.getByRole('button', { name: 'Continue with email' }));

    await waitFor(() => expect(signInWithPassword).toHaveBeenCalled());
    expect(signInWithPassword.mock.calls[0][0]).toMatchObject({ remember_me: false });
  });

  it('sends remember_me when the box is checked', async () => {
    const user = userEvent.setup();
    const checkbox = await renderCard();
    await fillCredentials(user);
    await user.click(checkbox);

    await user.click(screen.getByRole('button', { name: 'Continue with email' }));

    await waitFor(() => expect(signInWithPassword).toHaveBeenCalled());
    expect(signInWithPassword.mock.calls[0][0]).toMatchObject({ remember_me: true });
  });

  it('governs the Google button as well as the email form', async () => {
    const user = userEvent.setup();
    const checkbox = await renderCard();
    await user.click(checkbox);

    await user.click(screen.getByRole('button', { name: /continue with google/i }));

    expect(beginOAuth).toHaveBeenCalledWith('google', '/auth/callback', { remember: true });
  });

  it('is not offered while creating an account', async () => {
    const user = userEvent.setup();
    await renderCard();

    await user.click(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.queryByRole('checkbox', { name: /remember me/i })).toBeNull();
  });
});
