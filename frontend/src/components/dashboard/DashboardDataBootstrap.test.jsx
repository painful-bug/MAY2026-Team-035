import { act, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAppStore } from '../../store/appStore.js';
import { SESSION_STATUS, useAuthStore } from '../../store/authStore.js';
import DashboardDataBootstrap from './DashboardDataBootstrap.jsx';

const mocks = vi.hoisted(() => ({
  getDashboardSnapshot: vi.fn(),
  subscribeToDashboard: vi.fn(),
  unsubscribe: vi.fn(),
}));

vi.mock('../../lib/dashboard/dashboardApi.js', () => ({
  getDashboardSnapshot: mocks.getDashboardSnapshot,
  subscribeToDashboard: mocks.subscribeToDashboard,
}));

beforeEach(() => {
  mocks.getDashboardSnapshot.mockReset().mockResolvedValue({
    users: [{ id: 'resident-1' }],
  });
  mocks.unsubscribe.mockReset();
  mocks.subscribeToDashboard.mockReset().mockReturnValue(mocks.unsubscribe);
  useAppStore.getState().clearDashboard();
  useAuthStore.setState({
    currentUser: { id: 'admin-1', role: 'Admin' },
    isAuthReady: true,
    sessionStatus: SESSION_STATUS.MEMBER,
  });
});

afterEach(() => {
  useAppStore.getState().clearDashboard();
  useAuthStore.setState({
    currentUser: null,
    isAuthReady: false,
    sessionStatus: SESSION_STATUS.LOADING,
  });
});

describe('DashboardDataBootstrap', () => {
  it('closes its stream and clears the admin projection on unmount', async () => {
    const view = render(<DashboardDataBootstrap />);

    await waitFor(() => expect(useAppStore.getState().users).toEqual([{ id: 'resident-1' }]));
    expect(mocks.subscribeToDashboard).toHaveBeenCalledOnce();

    view.unmount();

    expect(mocks.unsubscribe).toHaveBeenCalledOnce();
    expect(useAppStore.getState().users).toEqual([]);
  });

  it('refreshes the projection when the stream reports a change', async () => {
    let onChange;
    mocks.getDashboardSnapshot
      .mockResolvedValueOnce({ users: [{ id: 'resident-1' }] })
      .mockResolvedValueOnce({ users: [{ id: 'resident-2' }] });
    mocks.subscribeToDashboard.mockImplementation((listener) => {
      onChange = listener;
      return mocks.unsubscribe;
    });
    render(<DashboardDataBootstrap />);
    await waitFor(() => expect(useAppStore.getState().users).toEqual([{ id: 'resident-1' }]));

    act(() => onChange());

    await waitFor(() => expect(useAppStore.getState().users).toEqual([{ id: 'resident-2' }]));
    expect(mocks.getDashboardSnapshot).toHaveBeenCalledTimes(2);
  });
});
