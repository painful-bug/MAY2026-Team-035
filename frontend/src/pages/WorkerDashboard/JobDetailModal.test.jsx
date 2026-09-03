import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import JobDetailModal from './JobDetailModal';

// Pins the portal contract for the worker job sheet. WorkerLayout's <main>
// carries no animation today, so this overlay was never trapped the way the
// admin and resident ones were (`animate-fade-in`'s fill-forwards opacity
// animation keeps <main> a permanent stacking context) — the portal to
// document.body is what keeps that true if anyone ever animates the layout.

const mocks = vi.hoisted(() => ({ job: vi.fn() }));

vi.mock('../../features/worker/workerApi', () => ({
  workerApi: {
    job: mocks.job,
    acceptJob: vi.fn(),
    declineJob: vi.fn(),
    startJob: vi.fn(),
    completeJob: vi.fn(),
    reportJobFailure: vi.fn(),
  },
}));

beforeEach(() => {
  mocks.job.mockReset().mockResolvedValue({
    id: 'wo-1',
    complaintTitle: 'Leaking tap',
    communityId: 'community-1',
    communityName: 'Green Acres',
    workOrderStatus: 'scheduled',
    assignmentStatus: 'offered',
    failedAttemptCount: 0,
  });
});

const renderSheet = (onClose = vi.fn()) =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <JobDetailModal workOrderId="wo-1" onClose={onClose} />
    </QueryClientProvider>
  );

describe('worker job sheet portal contract', () => {
  it('portals the dialog to document.body with a full-cover overlay', async () => {
    renderSheet();

    const dialog = await screen.findByRole('dialog', { name: 'Leaking tap' });
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog.className).toContain('fixed inset-0');
    // The panel scrolls internally instead of clipping.
    const panel = dialog.firstElementChild;
    expect(panel.className).toContain('overflow-y-auto');
    expect(panel.className).toContain('max-h-[90vh]');
  });

  it('keeps the close-button behavior', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderSheet(onClose);

    await screen.findByRole('dialog', { name: 'Leaking tap' });
    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
