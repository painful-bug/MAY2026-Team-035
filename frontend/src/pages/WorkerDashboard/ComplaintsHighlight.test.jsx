import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WorkerComplaints from './Complaints';

// The supervisor's `?complaint=` deep link.
//
// `notify_complaint_staff` was widened to supervisor-rank roster holders on
// 2026-08-21, and `portalUrl.js` began sending their copy of
// `/admin/complaints?complaint=…` to `/worker/complaints` the same day — which
// stopped the click that did nothing and replaced it with a click that landed
// on the right screen and said nothing about which of forty rows it meant.
// `docs/potential issues/12` counts that as its own defect and it was recorded
// as the honest remainder of `14`. The product owner closed it: the deep link
// highlights here and on the admin screen both.
//
// Rendered against the real `DepartmentComplaintList` rather than a stub. The
// property worth pinning is not "a prop was passed" — that is a rename away
// from meaningless — but "the row the notification named is marked and the rest
// of the queue is still there", which only the component itself can answer.

const mocks = vi.hoisted(() => ({
  snapshot: vi.fn(),
  departmentComplaints: vi.fn(),
  departmentOptions: vi.fn(),
}));

vi.mock('../../features/worker/workerApi', () => ({
  workerApi: { snapshot: mocks.snapshot },
}));
vi.mock('../../features/complaints/routingApi', () => ({
  complaintRoutingApi: {
    departmentComplaints: mocks.departmentComplaints,
    departmentOptions: mocks.departmentOptions,
  },
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

const complaint = (id, title) => ({
  id,
  title,
  description: '',
  status: 'open',
  priority: 'medium',
  raisedBy: 'A resident',
});

// The card is the `<article>` the list draws per row; the ring lives on its
// className. Read through the title rather than by test id so the assertion
// fails if the row stops being rendered at all.
const cardFor = (title) => screen.getByText(title).closest('article');

beforeEach(() => {
  for (const fn of Object.values(mocks)) fn.mockReset();
  mocks.snapshot.mockResolvedValue({ provider: null, communities: [ENGAGEMENT] });
  mocks.departmentOptions.mockResolvedValue([]);
  mocks.departmentComplaints.mockResolvedValue([
    complaint('complaint-1', 'Corridor light out'),
    complaint('complaint-2', 'Kitchen tap leaking'),
  ]);
});

function renderAt(path) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <WorkerComplaints />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('the supervisor’s complaints screen', () => {
  it('rings the complaint the notification was about', async () => {
    renderAt('/worker/complaints?complaint=complaint-2');
    expect(await screen.findByText('Kitchen tap leaking')).toBeVisible();
    expect(cardFor('Kitchen tap leaking').className).toContain('border-indigo-400');
  });

  it('leaves the rest of the queue in view rather than filtering to one', async () => {
    // A list of one hides the fact that there are nine more waiting, and a
    // supervisor who followed a link still has a department to run.
    renderAt('/worker/complaints?complaint=complaint-2');
    expect(await screen.findByText('Corridor light out')).toBeVisible();
    expect(cardFor('Corridor light out').className).not.toContain('border-indigo-400');
  });

  it('rings nothing when the link carries no complaint', async () => {
    renderAt('/worker/complaints');
    expect(await screen.findByText('Kitchen tap leaking')).toBeVisible();
    for (const title of ['Corridor light out', 'Kitchen tap leaking']) {
      expect(cardFor(title).className).not.toContain('border-indigo-400');
    }
  });

  it('rings nothing when the named complaint is not in this department', async () => {
    // The parameter is a complaint id and this screen is one department's
    // queue, so the two can legitimately disagree — a supervisor moved off the
    // roster, a complaint transferred out. Nothing is marked, and nothing
    // pretends to be.
    renderAt('/worker/complaints?complaint=complaint-99');
    expect(await screen.findByText('Kitchen tap leaking')).toBeVisible();
    for (const title of ['Corridor light out', 'Kitchen tap leaking']) {
      expect(cardFor(title).className).not.toContain('border-indigo-400');
    }
  });

  it('still refuses the screen to a technician, link or no link', async () => {
    // The gate is the roster and not the query string. A rank-`member`
    // technician shares this portal and reaches a rewritten complaint link
    // whenever `notify_complaint_staff` names their department.
    mocks.snapshot.mockResolvedValue({
      provider: null,
      communities: [{ ...ENGAGEMENT, rank: 'member' }],
    });
    renderAt('/worker/complaints?complaint=complaint-2');
    expect(await screen.findByText(/Complaints are shown to supervisors/)).toBeVisible();
    expect(mocks.departmentComplaints).not.toHaveBeenCalled();
  });
});
