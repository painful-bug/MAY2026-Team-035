import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ChatDock from './ChatDock';

const mocks = vi.hoisted(() => ({
  threads: vi.fn(),
  snapshot: vi.fn(),
}));

vi.mock('../../features/messages/messagesApi', () => ({
  messagesApi: {
    threads: mocks.threads,
    thread: vi.fn(),
    recipients: vi.fn(),
    openThread: vi.fn(),
    send: vi.fn(),
  },
}));

vi.mock('../../features/worker/workerApi', () => ({
  workerApi: {
    snapshot: mocks.snapshot,
  },
}));

vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector) => selector({
    sessionContext: { identity: { id: 'profile-1', full_name: 'Ravi Kumar' } },
  }),
}));

const completeProvider = {
  id: 'provider-1',
  displayName: 'Ravi Kumar',
  latitude: 22.572645,
  longitude: 88.363892,
  skillIds: ['skill-plumbing'],
};

beforeEach(() => {
  mocks.threads.mockReset().mockResolvedValue([]);
  mocks.snapshot.mockReset();
  localStorage.clear();
});

function renderDock(path) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <ChatDock />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ChatDock worker registration gate', () => {
  it('hides the dock on the worker surface while the profile is incomplete', async () => {
    mocks.snapshot.mockResolvedValue({ provider: null, communities: [] });
    renderDock('/worker');

    // Wait for the snapshot to settle so the absence is the gate's verdict,
    // not the pending state's.
    await waitFor(() => expect(mocks.snapshot).toHaveBeenCalled());
    await waitFor(() => expect(mocks.threads).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Open messages' })).not.toBeInTheDocument();
  });

  it('shows the dock on the worker surface for a registered provider, hired or not', async () => {
    mocks.snapshot.mockResolvedValue({ provider: completeProvider, communities: [] });
    renderDock('/worker/communities');

    expect(await screen.findByRole('button', { name: 'Open messages' })).toBeVisible();
  });

  it('shows the dock on non-worker paths without ever fetching the worker snapshot', async () => {
    renderDock('/resident/dashboard');

    expect(await screen.findByRole('button', { name: 'Open messages' })).toBeVisible();
    expect(mocks.snapshot).not.toHaveBeenCalled();
  });
});
