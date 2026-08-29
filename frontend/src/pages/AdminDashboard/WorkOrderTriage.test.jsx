import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WorkOrderTriage from './WorkOrderTriage';

// One live job per complaint, drawn before the button
// (`docs/plans/ONE_LIVE_JOB_SPEC.md`, owner ruling 2026-08-27).
//
// The bug this pins was live: a complaint collected a second
// `awaiting_resident` job fifteen seconds after the resident had booked the
// first one's visit, because the raise form sat under a list that already
// showed the live job and said nothing about it. The database refuses that
// raise now (`20260827210000_one_live_job_per_complaint.sql`, `HB409`); these
// tests are about the *other* half — that a supervisor is not offered a form
// whose only possible outcome is a 409.
//
// Four properties are pinned:
//
//   * a live job replaces the form with the frozen sentence. The sentence is
//     asserted verbatim because it is frozen in the spec and the same words the
//     SQL raises, so the two surfaces cannot drift apart;
//   * terminal jobs are not live — `completed`, `failed` and `cancelled` are
//     exactly the three states the guard lets through, and a screen that
//     treated any job as blocking would strand every closed complaint;
//   * no jobs at all still renders the form. That is the ordinary case;
//   * **no answer is not the same as "no live job"**: while the list is loading
//     or has failed, the form is absent. A form drawn in that window is the
//     duplicate-raise window itself, and it is the one property a
//     naive `jobs.data?.find(...)` implementation gets wrong.

const mocks = vi.hoisted(() => ({ api: vi.fn(), state: {} }));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));
vi.mock('../../store/useApp', () => ({
  useApp: (selector) => (selector ? selector(mocks.state) : mocks.state),
}));

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
  id: 'dept-1',
  name: 'Plumbing',
  skills: ['Plumber'],
  skillIds: ['skill-1'],
  staff: [],
};

const job = (status, overrides = {}) => ({
  id: `work-order-${status}`,
  status,
  scheduledStartAt: null,
  scheduledEndAt: null,
  assigneeName: null,
  ...overrides,
});

const FORM_HEADING = 'Raise a job against this complaint';
// Frozen copy — `ONE_LIVE_JOB_SPEC.md` §3, and the same sentence
// `create_work_order` raises with `HB409`.
const LIVE_NOTICE =
  'A job is already live on this complaint. Finish it, fail it, or cancel it before raising another.';

/**
 * Answer every read the raise tab makes; only the complaint's job list varies.
 *
 * `complaintJobs` is a *thunk* rather than an array so a test can hand back a
 * promise that never settles (pending) or one that rejects (errored) — the two
 * states in which this component does not yet know whether a job is live.
 */
function serve(complaintJobs = () => Promise.resolve([])) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path, options) => {
    if (path.startsWith('/departments/dept-1/complaints')) {
      return Promise.resolve([COMPLAINT]);
    }
    if (path.startsWith('/departments/dept-1/work-orders')) {
      return Promise.resolve([]);
    }
    if (path === '/departments/dept-1') {
      return Promise.resolve(DEPARTMENT);
    }
    if (path === '/complaints/complaint-1/work-orders') {
      // One path, two operations: the complaint's job list and the raise. Only
      // the second one carries a method.
      if (options?.method === 'POST') return Promise.resolve({ id: 'work-order-9' });
      return complaintJobs();
    }
    if (path === '/work-orders/work-order-awaiting_resident') {
      // The detail `JobDetail` fetches once the panel's button sets `?job=`.
      return Promise.resolve({
        id: 'work-order-awaiting_resident',
        status: 'awaiting_resident',
        priority: 'high',
        subjectKind: 'resident',
        complaintTitle: COMPLAINT.title,
        scheduledStartAt: null,
        scheduledEndAt: null,
        assignments: [],
      });
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
}

function renderRaiseTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[
          '/admin/departments/dept-1/work-orders?tab=raise&complaint=complaint-1',
        ]}
      >
        <Routes>
          <Route
            path="/admin/departments/:departmentId/work-orders"
            element={<WorkOrderTriage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  // The complaint card is expanded by `?complaint=`, so `ComplaintWorkOrders`
  // is mounted as soon as the complaints list lands.
  return screen.findByText('Jobs already raised');
}

beforeEach(() => {
  mocks.api.mockReset();
  // `portal`, not a display role: `homeRouteFor` reads the key the backend
  // computed, and anything else rebases every link on the screen.
  mocks.state = { currentUser: { portal: 'admin', departmentId: null } };
});

describe('the raise form is gated on the complaint having no live job', () => {
  it('replaces the form with the frozen sentence when a job is live', async () => {
    serve(() => Promise.resolve([job('awaiting_resident')]));
    await renderRaiseTab();

    expect(await screen.findByText(LIVE_NOTICE)).toBeVisible();
    expect(screen.queryByText(FORM_HEADING)).not.toBeInTheDocument();
    // Nothing to press: the raise button goes with the form it submitted.
    expect(screen.queryByRole('button', { name: /Raise it/ })).not.toBeInTheDocument();
    // The state is named, so the supervisor knows which lever closes it — the
    // panel otherwise says "a job" about a list the same panel is under.
    expect(
      screen.getByRole('button', { name: 'Open the live job — Waiting on the resident' }),
    ).toBeVisible();
  });

  it('opens the live job directly from the panel (owner ruling 2026-08-28)', async () => {
    // The button reuses the same `onOpenJob` the jobs-already-raised list
    // calls, which sets `?job=` — so the real proof is that the live job's
    // detail actually opens, the same way it would from that list.
    serve(() => Promise.resolve([job('awaiting_resident')]));
    await renderRaiseTab();

    const user = userEvent.setup();
    await user.click(
      await screen.findByRole('button', { name: 'Open the live job — Waiting on the resident' }),
    );

    expect(await screen.findByRole('heading', { name: COMPLAINT.title })).toBeVisible();
    expect(screen.getByLabelText('Close this job')).toBeVisible();
  });

  it('renders the form when every job on the complaint is terminal', async () => {
    serve(() => Promise.resolve([job('completed'), job('cancelled')]));
    await renderRaiseTab();

    expect(await screen.findByText(FORM_HEADING)).toBeVisible();
    expect(screen.queryByText(LIVE_NOTICE)).not.toBeInTheDocument();
  });

  it('renders the form when the complaint has no jobs at all', async () => {
    serve(() => Promise.resolve([]));
    await renderRaiseTab();

    expect(await screen.findByText(FORM_HEADING)).toBeVisible();
    expect(screen.queryByText(LIVE_NOTICE)).not.toBeInTheDocument();
  });

  it('draws no form while the job list is still loading', async () => {
    // A promise that never settles is the real first frame of every one of the
    // cases above, and the frame the duplicate raise was made in.
    serve(() => new Promise(() => {}));
    await renderRaiseTab();

    expect(screen.getByText('Loading…')).toBeVisible();
    expect(screen.queryByText(FORM_HEADING)).not.toBeInTheDocument();
    expect(screen.queryByText(LIVE_NOTICE)).not.toBeInTheDocument();
  });

  it('draws no form when the job list could not be read', async () => {
    serve(() => Promise.reject(new Error('The jobs on this complaint are unavailable.')));
    await renderRaiseTab();

    expect(
      await screen.findByText(/The jobs on this complaint are unavailable\./),
    ).toBeVisible();
    // An unreadable list is not evidence that nothing is live, so the form
    // stays away rather than defaulting open.
    expect(screen.queryByText(FORM_HEADING)).not.toBeInTheDocument();
  });
});
