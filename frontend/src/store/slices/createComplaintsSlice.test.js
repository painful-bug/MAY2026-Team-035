import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createComplaintsSlice } from './createComplaintsSlice';
import { api } from '../../lib/api/client';
import { getDashboardSnapshot } from '../../lib/dashboard/dashboardApi';

// What these tests pin: a write the server refused does not stay on screen.
//
// Both writers are optimistic — store first, server second — because the SSE
// re-snapshot normally replaces the optimistic copy with server truth within a
// beat. A *failed* write fires no SSE event, so the slice itself must correct
// the record: re-read the snapshot, or, when even that read fails, restore the
// one row to the last state the server agreed to. Before 2026-08-22 the catch
// only showed a toast and the refused state sat on the card indefinitely.

vi.mock('../../lib/api/client', () => ({ api: vi.fn() }));
vi.mock('../../lib/dashboard/dashboardApi', () => ({
  getDashboardSnapshot: vi.fn(),
}));
vi.mock('../authStore', () => ({
  useAuthStore: {
    getState: () => ({
      currentUser: { id: 'admin-1', name: 'Asha Admin', role: 'Admin' },
    }),
  },
}));

const pendingComplaint = () => ({
  id: 'c-1',
  title: 'Leaking tap',
  status: 'Pending',
  progress: 0,
  assignee: '',
  comments: [],
  timeline: [],
});

// The slice is written for zustand's (set, get); this is the same contract in
// ten lines, so the tests exercise the real slice functions without dragging
// in the whole composed appStore.
const buildStore = () => {
  let state;
  const set = (updater) => {
    state = {
      ...state,
      ...(typeof updater === 'function' ? updater(state) : updater),
    };
  };
  const get = () => state;
  state = {
    ...createComplaintsSlice(set, get),
    complaints: [pendingComplaint()],
    showToast: vi.fn(),
    addActivity: vi.fn(),
    hydrateDashboard: vi.fn((snapshot) => set({ complaints: snapshot.complaints })),
  };
  return get;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('updateComplaint', () => {
  it('keeps the optimistic state when the server accepts the write', async () => {
    const get = buildStore();
    api.mockResolvedValueOnce({ message: 'Complaint updated.' });

    await get().updateComplaint('c-1', { status: 'In Progress', progress: 10 });

    expect(get().complaints[0].status).toBe('In Progress');
    expect(get().showToast).toHaveBeenCalledWith('Updated complaint status', 'success');
    expect(getDashboardSnapshot).not.toHaveBeenCalled();
  });

  it('re-reads the snapshot when the server refuses the write', async () => {
    const get = buildStore();
    api.mockRejectedValueOnce(new Error('That status transition is not allowed.'));
    const serverTruth = { complaints: [pendingComplaint()] };
    getDashboardSnapshot.mockResolvedValueOnce(serverTruth);

    const result = await get().updateComplaint('c-1', { status: 'Resolved', progress: 100 });

    expect(result).toBeNull();
    expect(get().hydrateDashboard).toHaveBeenCalledWith(serverTruth);
    expect(get().complaints[0].status).toBe('Pending');
    expect(get().showToast).toHaveBeenCalledWith(
      'That status transition is not allowed.',
      'error'
    );
  });

  it('restores the row locally when the snapshot read fails too', async () => {
    const get = buildStore();
    api.mockRejectedValueOnce(new Error('Network request failed'));
    getDashboardSnapshot.mockRejectedValueOnce(new Error('Network request failed'));

    await get().updateComplaint('c-1', { status: 'Resolved', progress: 100 });

    expect(get().complaints[0]).toEqual(pendingComplaint());
  });
});

describe('addComplaintComment', () => {
  it('keeps the optimistic comment when the server accepts it', async () => {
    const get = buildStore();
    api.mockResolvedValueOnce({ message: 'Comment added.' });

    await get().addComplaintComment('c-1', 'Plumber booked for tomorrow.');

    expect(get().complaints[0].comments).toHaveLength(1);
    expect(get().showToast).toHaveBeenCalledWith('Comment added', 'success');
  });

  it('removes the optimistic comment when the server refuses it and the snapshot read fails', async () => {
    const get = buildStore();
    api.mockRejectedValueOnce(new Error('Network request failed'));
    getDashboardSnapshot.mockRejectedValueOnce(new Error('Network request failed'));

    const result = await get().addComplaintComment('c-1', 'Plumber booked.');

    expect(result).toBeNull();
    expect(get().complaints[0].comments).toHaveLength(0);
  });
});
