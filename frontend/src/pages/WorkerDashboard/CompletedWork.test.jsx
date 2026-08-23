import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CompletedWork from './CompletedWork';

// The archive (amendment 3, ruling B2). What these tests pin:
//
// - the read is the department queue with **no** status parameter, and the
//   ended rows are kept client-side — an `open` row from the same response
//   never renders;
// - the three end conditions carry their distinct labels, which exist on this
//   screen only ("Resolved — awaiting the resident", "Closed — confirmed",
//   "Cancelled") — the deliberate departure from the wire's closed→Resolved
//   folding, confined here;
// - the chips filter, the order is newest ending first, and the eye opens the
//   detail popup with nothing writable in it;
// - a technician gets the same refusal sentence as the other leadership pages.

const mocks = vi.hoisted(() => ({ api: vi.fn(), snapshot: vi.fn() }));
vi.mock('../../lib/api/client', () => ({ api: mocks.api }));
vi.mock('../../features/worker/workerApi', () => ({
  workerApi: { snapshot: mocks.snapshot },
}));

const ENGAGEMENT = {
  staffAssignmentId: 'staff-1',
  communityId: 'community-1',
  communityName: 'Green Meadows',
  departmentId: 'department-1',
  departmentName: 'Plumbing',
  rank: 'supervisor',
  status: 'active',
};

// Storage vocabulary, like the wire: `resolved`, not "Resolved".
const QUEUE = [
  {
    id: 'complaint-live',
    title: 'Tap still dripping',
    status: 'in_progress',
    priority: 'medium',
    createdAt: '2026-08-22T09:00:00.000Z',
  },
  {
    id: 'complaint-resolved',
    title: 'Sewage backing up',
    status: 'resolved',
    priority: 'high',
    category: 'Plumbing',
    location: 'Basement',
    raisedBy: 'Asha Devi',
    unitCode: 'B-402',
    createdAt: '2026-08-20T05:00:00.000Z',
    resolvedAt: '2026-08-21T05:00:00.000Z',
  },
  {
    id: 'complaint-closed',
    title: 'Geyser tripping the mains',
    status: 'closed',
    priority: 'medium',
    raisedBy: 'Ravi Kumar',
    createdAt: '2026-08-18T05:00:00.000Z',
    resolvedAt: '2026-08-22T05:00:00.000Z',
  },
  {
    id: 'complaint-cancelled',
    title: 'Wrong flat reported',
    status: 'cancelled',
    priority: 'low',
    createdAt: '2026-08-19T05:00:00.000Z',
    // No resolvedAt on purpose: the sort falls back to createdAt.
  },
];

const DETAIL = {
  complaint: {
    id: 'complaint-resolved',
    title: 'Sewage backing up',
    description: 'It has come up through the basement drain twice this week.',
    status: 'resolved',
    priority: 'high',
    created_at: '2026-08-20T05:00:00.000Z',
    resolved_at: '2026-08-21T05:00:00.000Z',
  },
  events: [
    {
      id: 'event-1',
      event_type: 'note_added',
      payload: { note: 'Riser was the real problem.', internal: true },
      created_at: '2026-08-20T06:00:00.000Z',
      message: 'Riser was the real problem.',
      actor_name: 'Meera Nair',
    },
  ],
};

beforeEach(() => {
  mocks.api.mockReset();
  mocks.snapshot.mockReset();
  mocks.snapshot.mockResolvedValue({ provider: null, communities: [ENGAGEMENT] });
  mocks.api.mockImplementation((path, options) => {
    if (path === '/departments/department-1/complaints' && !options) {
      return Promise.resolve(QUEUE);
    }
    if (path.startsWith('/complaints/staff/complaints/') && !options) {
      return Promise.resolve(DETAIL);
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <CompletedWork />
    </QueryClientProvider>,
  );
}

describe('the completed-work archive', () => {
  it('keeps only the ended rows, with no status parameter on the read', async () => {
    renderPage();

    expect(await screen.findByText('Sewage backing up')).toBeVisible();
    expect(screen.getByText('Geyser tripping the mains')).toBeVisible();
    expect(screen.getByText('Wrong flat reported')).toBeVisible();
    // The live row came in the same response and is filtered client-side.
    expect(screen.queryByText('Tap still dripping')).not.toBeInTheDocument();
    expect(mocks.api).toHaveBeenCalledWith('/departments/department-1/complaints');
  });

  it('labels the three end conditions distinctly, this screen only', async () => {
    renderPage();

    expect(await screen.findByText('Resolved — awaiting the resident')).toBeVisible();
    expect(screen.getByText('Closed — confirmed')).toBeVisible();
    // "Cancelled" is also a filter chip's word, so the assertion is scoped to
    // the card it belongs to.
    const cancelledCard = screen.getByText('Wrong flat reported').closest('article');
    expect(within(cancelledCard).getByText('Cancelled')).toBeVisible();
  });

  it('orders by when the complaint ended, newest first, createdAt as the fallback', async () => {
    renderPage();

    await screen.findByText('Sewage backing up');
    const titles = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    // closed 08-22, resolved 08-21, cancelled falls back to raised 08-19.
    expect(titles).toEqual([
      'Geyser tripping the mains',
      'Sewage backing up',
      'Wrong flat reported',
    ]);
  });

  it('filters by each end condition through the chips', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Sewage backing up');

    await user.click(screen.getByRole('button', { name: 'Resolved' }));
    expect(screen.getByText('Sewage backing up')).toBeVisible();
    expect(screen.queryByText('Geyser tripping the mains')).not.toBeInTheDocument();
    expect(screen.queryByText('Wrong flat reported')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Closed' }));
    expect(screen.getByText('Geyser tripping the mains')).toBeVisible();
    expect(screen.queryByText('Sewage backing up')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Cancelled' }));
    expect(screen.getByText('Wrong flat reported')).toBeVisible();
    expect(screen.queryByText('Geyser tripping the mains')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Everything' }));
    expect(screen.getByText('Sewage backing up')).toBeVisible();
    expect(screen.getByText('Geyser tripping the mains')).toBeVisible();
    expect(screen.getByText('Wrong flat reported')).toBeVisible();
  });

  it('opens the detail popup read-only: full timeline, nothing writable', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Sewage backing up');

    await user.click(screen.getByRole('button', { name: 'View details of Sewage backing up' }));

    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText(/come up through the basement drain/)).toBeVisible();
    // The look-back is the point: the internal note renders, marked.
    const note = within(dialog).getByText('Riser was the real problem.').closest('li');
    expect(within(note).getByText('Internal')).toBeVisible();
    // Nothing on this screen writes: no composer, no action rail.
    expect(within(dialog).queryByRole('textbox')).not.toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: 'Save note' })).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/What you can do from here/)).not.toBeInTheDocument();
  });

  it('speaks the archive label inside the popup too, for a closed complaint', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Geyser tripping the mains');

    await user.click(
      screen.getByRole('button', { name: 'View details of Geyser tripping the mains' }),
    );

    // The wire folds closed into "Resolved" everywhere else; the popup opened
    // from this screen is part of this screen, so its chip carries the
    // archive's distinct label instead.
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText('Closed — confirmed')).toBeVisible();
  });

  it('refuses a technician in the same words as the other leadership pages', async () => {
    mocks.snapshot.mockResolvedValue({
      provider: { id: 'provider-1' },
      communities: [{ ...ENGAGEMENT, rank: 'member' }],
    });
    renderPage();

    expect(
      await screen.findByText(/Completed work is shown to supervisors/),
    ).toBeVisible();
    // No department, no read.
    expect(mocks.api).not.toHaveBeenCalled();
  });
});
