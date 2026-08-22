import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ChatDock from './ChatDock';

const mocks = vi.hoisted(() => ({
  threads: vi.fn(),
  thread: vi.fn(),
  recipients: vi.fn(),
  snapshot: vi.fn(),
}));

vi.mock('../../features/messages/messagesApi', () => ({
  messagesApi: {
    threads: mocks.threads,
    thread: mocks.thread,
    recipients: mocks.recipients,
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
  mocks.thread.mockReset().mockResolvedValue({
    id: 'thread-9',
    kind: 'complaint',
    counterpartName: 'Asha Devi',
    communityName: 'Green Meadows',
    lockedAt: null,
    messages: [
      {
        id: 'message-1',
        authorProfileId: null,
        body: 'The department opened this chat about “Sewage backing up”.',
      },
    ],
  });
  mocks.recipients.mockReset().mockResolvedValue([]);
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

  it('shows the dock for leadership with no provider profile at all', async () => {
    // A supervisor was hired by an administrator typing their name — there is
    // no marketplace profile to complete. WorkerLayout lets them through on
    // the same test, and their dashboard's chat buttons open threads here.
    mocks.snapshot.mockResolvedValue({
      provider: null,
      communities: [{ status: 'active', rank: 'supervisor' }],
    });
    renderDock('/worker');

    expect(await screen.findByRole('button', { name: 'Open messages' })).toBeVisible();
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

// The supervisor triage dashboard opens a complaint's thread with
// `POST /complaints/{id}/chat` and then hands the dock the id it got back. The
// dock had two shapes for `hb:chat-open` — a community (New message) and
// nothing (the mailbox); this is the third.
describe('opening one specific thread from elsewhere in the app', () => {
  // jsdom implements no layout, so it has no `scrollIntoView` — the thread view
  // scrolls to the newest message on every render. A stub rather than a change
  // to the dock: the behaviour is right in a browser and untestable here.
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('opens straight into the conversation the detail names', async () => {
    renderDock('/resident/dashboard');
    await screen.findByRole('button', { name: 'Open messages' });

    act(() => {
      window.dispatchEvent(
        new CustomEvent('hb:chat-open', { detail: { threadId: 'thread-9' } }),
      );
    });

    // Not the mailbox and not the compose view: the thread itself, with its
    // seeded system line.
    expect(await screen.findByText(/opened this chat about/)).toBeVisible();
    expect(mocks.thread).toHaveBeenCalledWith('thread-9');
    expect(screen.getByRole('button', { name: 'Back to conversations' })).toBeVisible();
  });

  it('re-reads the mailbox, because the thread may be seconds old', async () => {
    renderDock('/resident/dashboard');
    await screen.findByRole('button', { name: 'Open messages' });
    const before = mocks.threads.mock.calls.length;

    act(() => {
      window.dispatchEvent(
        new CustomEvent('hb:chat-open', { detail: { threadId: 'thread-9' } }),
      );
    });

    // Otherwise Back lands on a list that does not contain the conversation
    // the supervisor is in.
    await waitFor(() => expect(mocks.threads.mock.calls.length).toBeGreaterThan(before));
  });

  it('still opens the compose view when the detail names a community', async () => {
    renderDock('/resident/dashboard');
    await screen.findByRole('button', { name: 'Open messages' });

    act(() => {
      window.dispatchEvent(
        new CustomEvent('hb:chat-open', { detail: { communityId: 'community-1' } }),
      );
    });

    expect(await screen.findByPlaceholderText(/start typing a name/)).toBeVisible();
  });
});
