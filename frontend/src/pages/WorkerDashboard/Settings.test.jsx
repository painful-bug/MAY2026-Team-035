import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WorkerSettings from './Settings';

// Pins the portal contract for the ask-to-leave modal. WorkerLayout's <main>
// carries no animation today, so this overlay was never trapped the way the
// admin and resident ones were (`animate-fade-in`'s fill-forwards opacity
// animation keeps <main> a permanent stacking context) — the portal to
// document.body is what keeps that true if anyone ever animates the layout.

const mocks = vi.hoisted(() => ({
  myCommunities: vi.fn(),
  pushSupported: vi.fn(() => false),
  pushEnabled: vi.fn(),
  enablePush: vi.fn(),
  disablePush: vi.fn(),
}));

// `snapshot` gates the whole page since the marketplace-profile split: with
// no `provider` on it the page renders `NoMarketplaceProfile` instead of the
// settings form, and with no stub at all react-query fails the render with
// "Missing queryFn". A provider is what puts the leave section on screen.
vi.mock('../../features/worker/workerApi', () => ({
  workerApi: {
    myCommunities: mocks.myCommunities,
    requestDeparture: vi.fn(),
    cancelDeparture: vi.fn(),
    snapshot: vi.fn().mockResolvedValue({ provider: { id: 'provider-1' } }),
    profile: vi.fn().mockResolvedValue({}),
    skills: vi.fn().mockResolvedValue([]),
    updateProfile: vi.fn(),
    setSkills: vi.fn(),
  },
}));

// Push needs a service worker registration jsdom does not have — false by
// default so the bulk of this file's tests see the "unsupported" card. The
// PushCard describe block below flips `pushSupported` on and exercises the
// interactive toggle and its failure paths.
vi.mock('../../lib/push/pushClient', () => ({
  pushSupported: mocks.pushSupported,
  pushEnabled: mocks.pushEnabled,
  enablePush: mocks.enablePush,
  disablePush: mocks.disablePush,
}));

// `sessionContext.identity`, not the older `sessionContext.user`: the page
// reads `identity.full_name` / `identity.email` since the OAuth identity model
// landed.
vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector) =>
    selector({
      sessionContext: {
        identity: { full_name: 'Anil Kumar', email: 'anil@example.com' },
      },
    }),
}));

beforeEach(() => {
  mocks.myCommunities.mockReset().mockResolvedValue([
    {
      staffAssignmentId: 'staff-1',
      communityId: 'community-1',
      communityName: 'Green Acres',
      departmentName: 'Maintenance',
      status: 'active',
      departure: null,
    },
  ]);
  mocks.pushSupported.mockReset().mockReturnValue(false);
  mocks.pushEnabled.mockReset().mockResolvedValue(false);
  mocks.enablePush.mockReset();
  mocks.disablePush.mockReset();
});

const renderPage = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <WorkerSettings />
    </QueryClientProvider>
  );

describe('ask-to-leave modal portal contract', () => {
  it('portals the dialog to document.body with a full-cover overlay', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      await screen.findByRole('button', { name: /ask to leave/i })
    );

    const dialog = screen.getByRole('dialog', { name: 'Leave Green Acres' });
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog.className).toContain('fixed inset-0');
    expect(dialog.className).toContain('z-[999]');
    // The panel scrolls internally on a short viewport instead of clipping.
    // `dvh`, not `vh`: the guard that landed on this panel independently
    // measures the dynamic viewport, so a mobile browser's collapsing URL bar
    // cannot push the panel's bottom out of reach. Kept as-is by the port.
    const panel = dialog.firstElementChild;
    expect(panel.className).toContain('overflow-y-auto');
    expect(panel.className).toContain('max-h-[calc(100dvh-2rem)]');
  });

  it('keeps the escape close behavior', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      await screen.findByRole('button', { name: /ask to leave/i })
    );
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

// PushCard resilience. The other suites in this file (and LeadershipScreens,
// SettingsLocation) all stub `pushSupported: () => false`, which means the
// interactive toggle path — the one with a real failure mode to guard against
// — has never actually run. These tests flip it on.
describe('PushCard resilience', () => {
  it('renders the interactive toggle, with no permanent spinner, when pushEnabled() rejects', async () => {
    mocks.pushSupported.mockReturnValue(true);
    mocks.pushEnabled.mockRejectedValue(new Error('boom'));
    renderPage();

    const toggle = await screen.findByRole('button', { name: /turn on/i });
    // The button renders (with its label) immediately, busy while the mount
    // effect's pushEnabled() call is still in flight — the assertion is on
    // what it settles to once that rejection is caught, not the first paint.
    await waitFor(() => expect(toggle).not.toBeDisabled());
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
  });

  it('renders the reason and clears busy when enablePush resolves { ok: false }', async () => {
    const user = userEvent.setup();
    mocks.pushSupported.mockReturnValue(true);
    mocks.pushEnabled.mockResolvedValue(false);
    mocks.enablePush.mockResolvedValue({
      ok: false,
      reason: 'Notifications are blocked. Allow them in your browser settings.',
    });
    renderPage();

    const toggle = await screen.findByRole('button', { name: /turn on/i });
    await user.click(toggle);

    expect(
      await screen.findByText('Notifications are blocked. Allow them in your browser settings.')
    ).toBeVisible();
    expect(screen.getByRole('button', { name: /turn on/i })).not.toBeDisabled();
  });
});
