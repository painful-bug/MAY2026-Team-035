import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WorkerWorkOrders from './WorkOrders';

// The dispatch queue inside the worker portal (product ruling, 2026-08-21).
//
// Four properties are pinned, and the first two are the whole feature:
//
//   * a supervisor reaches the *same* `WorkOrderTriage` the manager and the
//     admin portals mount, scoped to the department their roster row names —
//     not a copy of it, which is why the assertions here are about the real
//     screen's own words;
//   * a technician is refused in the Complaints screen's sentence rather than
//     by a page of failing requests. `member` is the rank marketplace hiring
//     produces, and it is the majority of this portal;
//   * the refusal is the same at both URLs. A guard that only covered the nav
//     item's path would be a guard somebody walks around by typing;
//   * `GET /departments/{id}` — which a `worker` membership may not call — does
//     not turn into a permission error under the queue. That read is context,
//     and every work-order endpoint admits the caller who cannot make it.

const mocks = vi.hoisted(() => ({ api: vi.fn(), state: {} }));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));
vi.mock('../../store/useApp', () => ({ useApp: () => mocks.state }));

const ENGAGEMENT = {
  staffAssignmentId: 'staff-1',
  communityId: 'community-1',
  communityName: 'Green Meadows',
  departmentId: 'department-1',
  departmentName: 'Plumbing',
  rank: 'supervisor',
  status: 'active',
};

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

/**
 * Answer every read this page makes, with the department detail refused.
 *
 * The 403 is not a pessimistic fixture, it is what production returns: the
 * departments router is guarded `require_admin_or_manager` and a
 * service-department supervisor holds a `worker` membership.
 */
function serve(communities, { jobs = [JOB] } = {}) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path) => {
    if (path === '/worker/snapshot') {
      return Promise.resolve({ provider: null, communities });
    }
    if (path.startsWith('/departments/department-1/work-orders')) {
      return Promise.resolve(jobs);
    }
    if (path.startsWith('/departments/department-1/complaints')) {
      return Promise.resolve([]);
    }
    if (path === '/departments/department-1') {
      return Promise.reject(
        Object.assign(
          new Error('You do not have permission for this community action.'),
          { code: 'community_role_required', status: 403 },
        ),
      );
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
}

function renderAt(path) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // The two routes App.jsx mounts under `/worker`, in the same shape.
  const router = createMemoryRouter(
    [
      { path: '/worker/work-orders', element: <WorkerWorkOrders /> },
      {
        path: '/worker/departments/:departmentId/work-orders',
        element: <WorkerWorkOrders />,
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
  mocks.state = { currentUser: { portal: 'worker', departmentId: null } };
});

describe('the supervisor dispatch queue in the worker portal', () => {
  it('lands a supervisor on their own department queue and renders the triage screen', async () => {
    serve([ENGAGEMENT]);
    const router = renderAt('/worker/work-orders');

    expect(await screen.findByText('Kitchen tap leaking')).toBeVisible();
    expect(
      screen.getByRole('heading', { name: 'Work orders', level: 1 }),
    ).toBeVisible();
    // The department id came off the roster row, not off the session — the
    // membership in this test carries none, which is the supervisor's case.
    expect(router.state.location.pathname).toBe(
      '/worker/departments/department-1/work-orders',
    );
    // Every cross-portal link is rebased by `usePortalScope`, so nothing on
    // this screen sends a supervisor into the admin portal.
    expect(screen.getByRole('link', { name: /Back to overview/ })).toHaveAttribute(
      'href',
      '/worker',
    );
  });

  it('carries a deep link on through the redirect', async () => {
    // `0037`'s supervisor notifications address a job by `?job=`, and the
    // landing path is the one a notification would reasonably use.
    serve([ENGAGEMENT]);
    const router = renderAt('/worker/work-orders?job=work-order-1&tab=queue');

    await screen.findByText('Kitchen tap leaking');
    expect(router.state.location.search).toBe('?job=work-order-1&tab=queue');
  });

  it('renders the queue for a supervisor who arrives at the department URL directly', async () => {
    serve([ENGAGEMENT]);
    renderAt('/worker/departments/department-1/work-orders');

    expect(await screen.findByText('Kitchen tap leaking')).toBeVisible();
  });

  it('says why a technician has no queue, and asks the API for none', async () => {
    serve([{ ...ENGAGEMENT, rank: 'member' }]);
    renderAt('/worker/work-orders');

    expect(
      await screen.findByText(/Work orders are shown to supervisors/),
    ).toBeVisible();
    expect(
      screen.queryByRole('heading', { name: 'Work orders', level: 1 }),
    ).not.toBeInTheDocument();
    const asked = mocks.api.mock.calls.map(([path]) => path);
    expect(asked).toEqual(['/worker/snapshot']);
  });

  it('refuses a technician at the department URL too', async () => {
    serve([{ ...ENGAGEMENT, rank: 'member' }]);
    renderAt('/worker/departments/department-1/work-orders');

    expect(
      await screen.findByText(/Work orders are shown to supervisors/),
    ).toBeVisible();
    expect(screen.queryByText('Kitchen tap leaking')).not.toBeInTheDocument();
  });

  it('refuses a marketplace professional on no roster at all', async () => {
    serve([]);
    renderAt('/worker/work-orders');

    expect(
      await screen.findByText(/Work orders are shown to supervisors/),
    ).toBeVisible();
  });

  it('ignores an ended supervisor posting', async () => {
    // The same rule the registration gate uses: `status` is on the roster row
    // because a posting that ended is not a posting.
    serve([{ ...ENGAGEMENT, status: 'ended' }]);
    renderAt('/worker/work-orders');

    expect(
      await screen.findByText(/Work orders are shown to supervisors/),
    ).toBeVisible();
  });

  it('does not show the department read’s 403 as a page failure', async () => {
    serve([ENGAGEMENT]);
    renderAt('/worker/work-orders');

    await screen.findByText('Kitchen tap leaking');
    expect(
      screen.queryByText(/do not have permission for this community action/),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/trade list could not be read/),
    ).toBeVisible();
  });
});
