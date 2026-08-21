import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SESSION_STATUS, useAuthStore } from '../../store/authStore';
import SessionRestorationState from './SessionRestorationState';

const initializeAuth = useAuthStore.getState().initializeAuth;

afterEach(() => {
  useAuthStore.setState({
    authError: '',
    initializeAuth,
    isAuthReady: false,
    sessionStatus: SESSION_STATUS.LOADING,
  });
});

describe('SessionRestorationState', () => {
  it('shows one shared loading state', () => {
    render(<SessionRestorationState />);
    expect(screen.getByText('Restoring your session…')).toBeInTheDocument();
  });

  it('keeps a backend failure retryable instead of showing signed-out UI', () => {
    const retry = vi.fn();
    useAuthStore.setState({
      authError: 'The server did not respond in time. Please try again.',
      initializeAuth: retry,
      isAuthReady: true,
      sessionStatus: SESSION_STATUS.ERROR,
    });

    render(<SessionRestorationState />);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));

    expect(screen.getByRole('alert')).toHaveTextContent('The server did not respond in time');
    expect(retry).toHaveBeenCalledOnce();
  });
});
