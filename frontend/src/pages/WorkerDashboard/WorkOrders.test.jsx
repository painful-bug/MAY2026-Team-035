import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
vi.mock('../../store/useApp', () => ({
  useApp: (selector) => (selector ? selector(mocks.state) : mocks.state),
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

/**
 * Answer every read this page makes, with the department detail refused.
 *
 * The 403 is not a pessimistic fixture, it is what production returns: the
 * departments router is guarded `require_admin_or_manager` and a
 * service-department supervisor holds a `worker` membership.
 */
function serve(communities, { jobs = [JOB], complaints = [] } = {}) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path, options) => {
    if (path === '/worker/snapshot') {
      return Promise.resolve({ provider: null, communities });
    }
    if (path.startsWith('/departments/department-1/work-orders')) {
      return Promise.resolve(jobs);
    }
    if (path.startsWith('/departments/department-1/complaints')) {
      return Promise.resolve(complaints);
    }
    if (path === '/complaints/complaint-1/work-orders') {
      // The same path is the complaint's job list and the raise. Only the
      // second one carries a method.
      return Promise.resolve(options?.method === 'POST' ? { id: 'work-order-9' } : []);
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

// Ruling F1 (`docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md`): the raise form asks
// *what* and *where* and no longer asks *when*, for anybody. Who answers "when"
// is decided by who the job is about — the resident for their own home, the
// system for a common area — and the two sentences the form prints are the only
// place a supervisor is told that.
describe('raising a job no longer asks for the hour', () => {
  const openRaiseTab = async () => {
    serve([ENGAGEMENT], { complaints: [COMPLAINT] });
    renderAt(
      '/worker/departments/department-1/work-orders?tab=raise&complaint=complaint-1',
    );
    return screen.findByText('Raise a job against this complaint');
  };

  it('draws no date or time input at all', async () => {
    await openRaiseTab();

    // The strongest form of the assertion available: not "the labels are gone"
    // but "there is nowhere on this screen to type an hour".
    expect(document.querySelectorAll('input[type="datetime-local"]')).toHaveLength(0);
    expect(screen.queryByText(/Start \(optional\)/)).not.toBeInTheDocument();
    expect(screen.queryByText(/End \(optional\)/)).not.toBeInTheDocument();
    // And the old fork's explanation went with them.
    expect(screen.queryByText(/this stays a draft/)).not.toBeInTheDocument();
  });

  it('tells the supervisor who picks the time, and changes its answer with the subject', async () => {
    const user = userEvent.setup();
    await openRaiseTab();

    expect(
      screen.getByText(
        /The resident picks the visit time — this sends them the request\. If they have not answered in 24 hours, the system books the first free hour a serviceman can take\./,
      ),
    ).toBeVisible();

    // Two selects in the form and the subject is the first: "At somebody's
    // home" or "A common area".
    await user.selectOptions(screen.getAllByRole('combobox')[0], 'facility');

    expect(
      screen.getByText(
        /Nobody confirms a common-area job — the system books the first free hour a serviceman can take, once urgent home visits are covered\./,
      ),
    ).toBeVisible();
  });

  it('sends a payload with no slot keys in it', async () => {
    const user = userEvent.setup();
    await openRaiseTab();

    await user.type(
      screen.getByPlaceholderText(/Where \(Flat B-402/),
      'Flat B-402',
    );
    await user.click(screen.getByRole('button', { name: /Raise it/ }));

    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-1/work-orders', {
        method: 'POST',
        body: JSON.stringify({
          subjectKind: 'resident',
          skillId: null,
          locationText: 'Flat B-402',
          note: null,
        }),
      }));

    // Belt and braces: the wire body is checked for the two words themselves,
    // because a null `scheduledStartAt` is not the same request as an absent
    // one — the server forks on presence (adjudication G1).
    const [, options] = mocks.api.mock.calls.find(
      ([path, opts]) => path === '/complaints/complaint-1/work-orders' && opts?.method === 'POST',
    );
    expect(options.body).not.toContain('scheduledStartAt');
    expect(options.body).not.toContain('scheduledEndAt');
  });
});
