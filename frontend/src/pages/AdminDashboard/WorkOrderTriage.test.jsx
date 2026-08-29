import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WorkOrderTriage from './WorkOrderTriage';

// The department-detail read, portal by portal.
//
// `GET /departments/{id}` is guarded `require_admin_or_manager`
// (`departments.py:47`). The admin and manager portals may make it and this
// screen leans on it for the trade list; the worker portal's supervisor holds
// a `worker` membership and may not, so the screen never asks there —
// `WorkerDashboard/WorkOrders.test.jsx` pins that side. This file pins the
// other: gating the worker portal off did not cost the admin their read.

const mocks = vi.hoisted(() => ({ api: vi.fn(), state: {} }));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));
vi.mock('../../store/useApp', () => ({ useApp: () => mocks.state }));

const JOB = {
  id: 'work-order-1',
  complaintTitle: 'Kitchen tap leaking',
  complaintCategory: 'Plumbing',
  skillName: 'Plumber',
  status: 'offered',
  priority: 'high',
  subjectKind: 'resident',
  locationText: 'Flat B-402',
  scheduledStartAt: null,
  scheduledEndAt: null,
  assigneeName: null,
  failedAttemptCount: 0,
};

const COMPLAINT = {
  id: 'complaint-1',
  title: 'Kitchen tap leaking',
  raisedBy: 'Asha Devi',
  unitCode: 'B-402',
  category: 'Plumbing',
  priority: 'high',
  status: 'in_progress',
};

const DEPARTMENT = {
  id: 'department-1',
  name: 'Plumbing',
  staff: [{ id: 'staff-1', name: 'Ravi Kumar', status: 'active' }],
  skills: ['Plumber'],
  skillIds: ['skill-1'],
};

function serve({ jobs = [JOB], complaints = [COMPLAINT] } = {}) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path, options) => {
    if (path.startsWith('/departments/department-1/work-orders')) {
      return Promise.resolve(jobs);
    }
    if (path.startsWith('/departments/department-1/complaints')) {
      return Promise.resolve(complaints);
    }
    if (path === '/departments/department-1') {
      return Promise.resolve(DEPARTMENT);
    }
    if (path === '/complaints/complaint-1/work-orders' && !options?.method) {
      return Promise.resolve([]);
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
}

function renderAt(path) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      {
        path: '/admin/departments/:departmentId/work-orders',
        element: <WorkOrderTriage />,
      },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

beforeEach(() => {
  mocks.api.mockReset();
  mocks.state = { currentUser: { portal: 'admin', departmentId: null } };
});

describe('the department-detail read under the admin portal', () => {
  it('still asks for it, and offers its trades in the raise form', async () => {
    serve();
    renderAt('/admin/departments/department-1/work-orders?tab=raise&complaint=complaint-1');

    await screen.findByText('Raise a job against this complaint');
    const asked = mocks.api.mock.calls.map(([path]) => path);
    expect(asked).toContain('/departments/department-1');
    // The trade list came off the read, so the raise form has it to offer.
    expect(
      await screen.findByRole('option', { name: 'Plumber' }),
    ).toBeInTheDocument();
    // And the "not available here" note is the worker portal's, not this one's.
    expect(
      screen.queryByText(/trade list is not available here/),
    ).not.toBeInTheDocument();
  });

  it('keeps the note for a genuine failure of the read', async () => {
    serve();
    mocks.api.mockImplementation((path) => (
      path === '/departments/department-1'
        ? Promise.reject(Object.assign(new Error('boom'), { status: 500 }))
        : Promise.resolve(path.includes('/work-orders') ? [JOB] : [])
    ));
    renderAt('/admin/departments/department-1/work-orders');

    await screen.findByText('Kitchen tap leaking');
    expect(
      await screen.findByText(/trade list is not available here/),
    ).toBeVisible();
  });
});
