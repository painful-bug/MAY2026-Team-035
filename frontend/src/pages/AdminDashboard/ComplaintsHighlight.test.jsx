import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AdminComplaints from './Complaints';

// The admin's `?complaint=` deep link.
//
// Eight notification call sites across three surviving migrations write
// `/admin/complaints?complaint={id}` and this screen read none of them, so the
// reader arrived at up to two hundred cards with nothing saying which one they
// had been told about. Right screen,
// wrong row — the defect `backend/tests/test_notification_links.py` counts in
// `IGNORED_QUERY_PARAMETERS`, and the entry for this path left that set with
// this change.
//
// The two properties worth pinning are the ones a ring is easy to get wrong:
// **exactly one card is marked**, and **the queue is still whole**. Filtering
// down to the linked complaint would look like a better answer and would hide
// the nine behind it.

const mocks = vi.hoisted(() => ({ state: {} }));

vi.mock('../../store/useApp', () => ({
  useApp: (selector) => (selector ? selector(mocks.state) : mocks.state),
}));
// The raise modal is a screen of its own with its own reads, and nothing here
// opens it.
vi.mock('../../features/complaints/components/AdminRaiseComplaintModal', () => ({
  default: () => null,
}));
vi.mock('../../lib/dashboard/dashboardApi', () => ({
  getDashboardSnapshot: vi.fn(),
}));

const complaint = (id, title) => ({
  id,
  title,
  description: 'Something needs doing.',
  status: 'Pending',
  urgency: 'Medium',
  progress: 0,
  assignee: '',
  flat: 'A-101',
  raisedBy: 'A resident',
  date: '21 Aug 2026',
  timeAgo: 'today',
  comments: [],
});

const baseState = () => ({
  complaints: [
    complaint('complaint-1', 'Corridor light out'),
    complaint('complaint-2', 'Kitchen tap leaking'),
    complaint('complaint-3', 'Lift alarm sticking'),
  ],
  updateComplaint: vi.fn(),
  addComplaintComment: vi.fn(),
  hydrateDashboard: vi.fn(),
  showToast: vi.fn(),
});

// The card is the outermost `<div>` of the row; `aria-current` is what says
// "this is the one you were told about" to a reader who cannot see the ring, so
// it is also the honest thing to assert on.
const cardFor = (title) => screen.getByText(title).closest('div[class*="rounded-2xl"]');
const marked = () => document.querySelectorAll('[aria-current="true"]');

function renderAt(path) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AdminComplaints />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  mocks.state = baseState();
});

describe('the admin complaints screen', () => {
  it('rings the complaint the notification was about', () => {
    renderAt('/admin/complaints?complaint=complaint-2');

    expect(marked()).toHaveLength(1);
    expect(marked()[0].textContent).toContain('Kitchen tap leaking');
    expect(cardFor('Kitchen tap leaking').className).toContain('border-indigo-400');
  });

  it('leaves the rest of the queue in view rather than filtering to one', () => {
    renderAt('/admin/complaints?complaint=complaint-2');

    for (const title of ['Corridor light out', 'Kitchen tap leaking', 'Lift alarm sticking']) {
      expect(screen.getByText(title)).toBeVisible();
    }
    expect(cardFor('Lift alarm sticking').className).not.toContain('border-indigo-400');
  });

  it('marks nothing when the link carries no complaint', () => {
    renderAt('/admin/complaints');

    expect(marked()).toHaveLength(0);
    expect(cardFor('Kitchen tap leaking').className).toContain('border-slate-100');
  });

  it('marks nothing when the named complaint is not in the community', () => {
    // A row older than the snapshot's 200-row cap, or one raised in a community
    // the reader has since left. Nothing is marked, and nothing pretends to be.
    renderAt('/admin/complaints?complaint=complaint-99');

    expect(marked()).toHaveLength(0);
  });

  it('marks nothing for an empty parameter rather than every card', () => {
    // `?complaint=` with no value reads back as the empty string, and a naive
    // equality against a complaint with no id would ring the lot.
    mocks.state = {
      ...baseState(),
      complaints: [{ ...complaint('', 'A row with no id'), id: '' }],
    };
    renderAt('/admin/complaints?complaint=');

    expect(marked()).toHaveLength(0);
  });
});
