import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WorkerLanding from './WorkerLanding';

// The supervisor triage dashboard, and the fork that decides who sees it.
//
// **Everything here is mocked at the HTTP boundary and that is not a shortcut.**
// `GET /departments/{id}/triage-snapshot` and `POST /complaints/{id}/take-up`
// do not exist on the running backend yet — the migration that adds
// `taken_up_at`, `started_at` and `supervision_inherited_at` is hand-applied by
// the owner. So the contract in `docs/plans/SUPERVISOR_TRIAGE_SPEC.md` is what
// these fixtures are written against, and these tests are the only thing
// holding the page to it until the endpoints land.
//
// What is pinned:
//
//   * the landing fork, in both directions. A technician's `/worker` is
//     unchanged, and their browser asks for no triage snapshot at all;
//   * the page renders the server's five arrays and re-buckets none of them.
//     The bucketing rules are intricate (amendment 2's *furthest stage wins*: a
//     complaint with a live job appears only as that job, and an offered-but-
//     unaccepted one is an *open request* rather than an assignment), and a
//     second copy of them in the browser is the failure this asserts against;
//   * the urgent stack is pinned client-side — a sort inside section 1 that
//     moves nothing between sections;
//   * every stage verb posts to the right complaint, and every refusal lands on
//     the card it belongs to, verbatim;
//   * the three universal actions are on every card in every section, and the
//     force-assign is labelled as what it is.

const mocks = vi.hoisted(() => ({ api: vi.fn() }));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));
// The portal base for the "Raise job request" deep link. `usePortalScope` reads
// it off the session, which no test renders — the real one is `/worker`.
vi.mock('../../store/useApp', () => ({
  useApp: () => ({ currentUser: { portal: 'worker', departmentId: null } }),
}));

const SUPERVISOR = {
  staffAssignmentId: 'staff-1',
  communityId: 'community-1',
  communityName: 'Green Meadows',
  departmentId: 'department-1',
  departmentName: 'Plumbing',
  rank: 'supervisor',
  status: 'active',
};

const TECHNICIAN = { ...SUPERVISOR, staffAssignmentId: 'staff-2', rank: 'member' };

const ORDINARY = {
  id: 'complaint-ordinary',
  title: 'Corridor light flickering',
  category: 'Electrical',
  priority: 'Medium',
  status: 'Pending',
  location: 'Block B corridor',
  raisedBy: 'Asha Devi',
  unitCode: 'B-402',
  createdAt: '2026-08-22T06:00:00.000Z',
  dueAt: null,
  returnedToPoolAt: null,
  reopenedCount: 0,
  reroutedAt: null,
  takenUpAt: null,
  takenUpByName: null,
  liveWorkOrderCount: 0,
  openRequestId: null,
};

const URGENT = {
  ...ORDINARY,
  id: 'complaint-urgent',
  title: 'Sewage backing up',
  category: 'Plumbing',
  priority: 'High',
  createdAt: '2026-08-22T05:00:00.000Z',
};

const BOUNCED = {
  ...ORDINARY,
  id: 'complaint-bounced',
  title: 'Tap dripping since Tuesday',
  category: 'Plumbing',
  priority: 'Low',
  returnedToPoolAt: '2026-08-21T10:00:00.000Z',
  reopenedCount: 2,
  reroutedAt: '2026-08-20T10:00:00.000Z',
  createdAt: '2026-08-21T05:00:00.000Z',
};

// Deliberately High. It is in `takenUp` because the server put it there, and
// nothing in the browser is allowed to lift it into the urgent stack.
const ALREADY_MINE = {
  ...ORDINARY,
  id: 'complaint-mine',
  title: 'Lift making a noise',
  priority: 'High',
  status: 'In Progress',
  takenUpAt: '2026-08-22T07:00:00.000Z',
  takenUpByName: 'Ravi Kumar',
};

// Section 3, the amendment's new one: raised, offered, nobody has said yes.
// Ruling A3 is why it is not in "Assigned, work pending".
const OPEN_REQUEST = {
  id: 'work-order-3',
  complaintId: 'complaint-open',
  complaintTitle: 'Gate motor jammed',
  complaintCategory: 'Electrical',
  priority: 'Medium',
  status: 'offered',
  assigneeName: null,
  offeredToName: 'Meena Rao',
  scheduledStartAt: '2026-08-23T04:00:00.000Z',
  scheduledEndAt: null,
  startedAt: null,
  inheritedAt: null,
  locationText: 'Main gate',
  skillName: 'Electrician',
};

// Already at the top of the scale, which is the state the priority button has
// to explain rather than error on.
const OPEN_REQUEST_HIGH = {
  ...OPEN_REQUEST,
  id: 'work-order-4',
  complaintId: 'complaint-open-high',
  complaintTitle: 'Basement pump dead',
  priority: 'High',
  status: 'draft',
  offeredToName: null,
  scheduledStartAt: null,
};

const BOOKED = {
  id: 'work-order-1',
  complaintId: 'complaint-booked',
  complaintTitle: 'Water tank overflow',
  complaintCategory: 'Plumbing',
  priority: 'High',
  status: 'scheduled',
  assigneeName: 'Anil Sharma',
  offeredToName: null,
  scheduledStartAt: '2026-08-23T04:00:00.000Z',
  scheduledEndAt: '2026-08-23T05:00:00.000Z',
  startedAt: null,
  // The v1 decision-3 badge, shipping here: this job's supervision was
  // re-stamped onto whoever is reading the screen when somebody left.
  inheritedAt: '2026-08-21T09:00:00.000Z',
  locationText: 'Terrace tank',
  skillName: 'Plumber',
};

const UNDER_WAY = {
  ...BOOKED,
  id: 'work-order-2',
  complaintId: 'complaint-under-way',
  complaintTitle: 'Pump room flooding',
  status: 'in_progress',
  inheritedAt: null,
  // Relative, because the card's clock is a real one.
  startedAt: new Date(Date.now() - 95 * 60_000).toISOString(),
};

const TRIAGE = {
  departmentId: 'department-1',
  newComplaints: [ORDINARY, URGENT, BOUNCED],
  takenUp: [ALREADY_MINE],
  openRequests: [OPEN_REQUEST, OPEN_REQUEST_HIGH],
  assignedPending: [BOOKED],
  inProgress: [UNDER_WAY],
};

const EMPTY_TRIAGE = {
  departmentId: 'department-1',
  newComplaints: [],
  takenUp: [],
  openRequests: [],
  assignedPending: [],
  inProgress: [],
};

/**
 * Answer every call this page can make, and nothing else.
 *
 * All of them are mocked because none of them is on the running backend yet;
 * an unexpected path rejects loudly rather than resolving to undefined, so a
 * request this page should not be making shows up as a failure.
 */
function serve({ communities = [SUPERVISOR], triage = TRIAGE, write } = {}) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path, options) => {
    if (path === '/worker/snapshot') {
      return Promise.resolve({
        provider: null,
        communities,
        pendingOffers: [],
        today: [],
        openJobCount: 0,
      });
    }
    if (path === '/departments/department-1/triage-snapshot') {
      return typeof triage === 'function' ? triage() : Promise.resolve(triage);
    }
    if (options?.method === 'POST') {
      if (write) {
        const answer = write(path, options);
        if (answer) return answer;
      }
      if (path.endsWith('/take-up')) return Promise.resolve({ message: 'Taken up.' });
      if (path.endsWith('/resolve')) return Promise.resolve({ message: 'Resolved.' });
      if (path.endsWith('/priority-raise')) return Promise.resolve({ message: 'Raised.' });
      if (path.endsWith('/notes')) return Promise.resolve({ message: 'Noted.' });
      if (path.endsWith('/chat')) return Promise.resolve({ threadId: 'thread-9' });
      if (path.endsWith('/assign')) return Promise.resolve({ message: 'Assigned.' });
    }
    if (path.startsWith('/complaints/staff/complaints/')) return Promise.resolve(STAFF_DETAIL);
    if (path.includes('/candidates')) return Promise.resolve(CANDIDATES);
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
}

// The staff detail is the database row, snake-cased and in storage vocabulary —
// it is not the resident DTO and not the snapshot's `TriageComplaint`.
const STAFF_DETAIL = {
  complaint: {
    id: 'complaint-urgent',
    title: 'Sewage backing up',
    description: 'It has come up through the basement drain twice.',
    category: 'Plumbing',
    priority: 'high',
    status: 'open',
    location: 'Basement',
    created_at: '2026-08-22T05:00:00.000Z',
    reopened_count: 0,
  },
  events: [
    {
      id: 'event-1',
      event_type: 'raised',
      payload: {},
      created_at: '2026-08-22T05:00:00.000Z',
      message: 'The complaint was submitted to the management team.',
    },
  ],
};

const CANDIDATES = [
  { staffAssignmentId: 'staff-9', displayName: 'Meena Rao', openJobs: 2, excluded: false },
];

function renderLanding() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: '/worker', element: <WorkerLanding /> }], {
    initialEntries: ['/worker'],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const triageCalls = () =>
  mocks.api.mock.calls.filter(([path]) => path === '/departments/department-1/triage-snapshot');

// Awaited, because the landing fork asks the worker snapshot who this is before
// it renders anything at all.
const sectionFor = async (name) =>
  (await screen.findByRole('heading', { name: new RegExp(name), level: 2 })).closest('section');

beforeEach(() => {
  mocks.api.mockReset();
});

describe('the worker portal landing fork', () => {
  it('lands department leadership on the triage dashboard', async () => {
    serve();
    renderLanding();

    expect(await screen.findByRole('heading', { name: 'Plumbing', level: 1 })).toBeVisible();
    expect(screen.getByText(/Green Meadows/)).toBeVisible();
    // All five section headers are on the page, empty or not — the shell is
    // the promise that the supervisor's whole day is on one screen.
    for (const title of [
      'New complaints', 'Taken up by you', 'Open job requests',
      'Assigned, work pending', 'Being worked right now',
    ]) {
      expect(screen.getByRole('heading', { name: new RegExp(title), level: 2 })).toBeVisible();
    }
  });

  it('leaves a technician on the unchanged worker home, and asks for no triage snapshot', async () => {
    serve({ communities: [TECHNICIAN] });
    renderLanding();

    expect(await screen.findByRole('heading', { name: /here is your day/, level: 1 })).toBeVisible();
    expect(screen.queryByRole('heading', { name: /New complaints/ })).not.toBeInTheDocument();
    expect(triageCalls()).toHaveLength(0);
  });

  it('leaves a marketplace professional on no roster at all on the worker home', async () => {
    serve({ communities: [] });
    renderLanding();

    expect(await screen.findByText('You are not on any roster yet')).toBeVisible();
    expect(triageCalls()).toHaveLength(0);
  });

  it('ignores an ended supervisor posting, exactly as the registration gate does', async () => {
    serve({ communities: [{ ...SUPERVISOR, status: 'ended' }] });
    renderLanding();

    expect(await screen.findByRole('heading', { name: /here is your day/, level: 1 })).toBeVisible();
    expect(triageCalls()).toHaveLength(0);
  });

  it('lands a manager there too — leadership is the rank pair, not one word', async () => {
    serve({ communities: [{ ...SUPERVISOR, rank: 'manager' }] });
    renderLanding();

    expect(await screen.findByRole('heading', { name: /New complaints/, level: 2 })).toBeVisible();
  });
});

describe('section 1 — new complaints', () => {
  it('renders every complaint the server put in the array, with its chips', async () => {
    serve();
    renderLanding();

    const section = await sectionFor('New complaints');
    await waitFor(() => expect(within(section).getByText('Sewage backing up')).toBeVisible());

    expect(within(section).getByText('Corridor light flickering')).toBeVisible();
    expect(within(section).getByText('Tap dripping since Tuesday')).toBeVisible();
    // The count on the header is the array's length and not a filtered view.
    expect((await sectionFor('New complaints')).querySelector('h2').textContent).toContain('3');

    // Both chips carry their word, so neither is colour-only.
    expect(within(section).getAllByText('High').length).toBeGreaterThan(0);
    expect(within(section).getByText('Medium')).toBeVisible();
    expect(within(section).getByText('Low')).toBeVisible();
    expect(within(section).getAllByText('Plumbing').length).toBe(2);
    expect(within(section).getByText('Electrical')).toBeVisible();
  });

  it('pins the urgent stack on top without moving anything between sections', async () => {
    serve();
    renderLanding();

    const section = await sectionFor('New complaints');
    await waitFor(() => expect(within(section).getByText('Sewage backing up')).toBeVisible());

    const order = within(section)
      .getAllByRole('heading', { level: 3 })
      .map((node) => node.textContent);
    // High first — and the two ordinary ones keep the server's own order
    // behind it. The server sorts newest-first; this is a stable partition.
    expect(order).toEqual([
      'Sewage backing up',
      'Corridor light flickering',
      'Tap dripping since Tuesday',
    ]);
    expect(within(section).getByText(/Urgent · 1/)).toBeVisible();
  });

  it('badges a complaint that came back, and says why', async () => {
    serve();
    renderLanding();

    const section = await sectionFor('New complaints');
    await waitFor(() => expect(within(section).getByText('Tap dripping since Tuesday')).toBeVisible());

    expect(within(section).getByText('Returned to pool')).toBeVisible();
    expect(within(section).getByText('Reopened ×2')).toBeVisible();
    expect(within(section).getByText('Moved to this department')).toBeVisible();
  });

  it('gives one category one colour across cards, and a different one to another trade', async () => {
    serve();
    renderLanding();

    const section = await sectionFor('New complaints');
    await waitFor(() => expect(within(section).getByText('Sewage backing up')).toBeVisible());

    const [plumbingA, plumbingB] = within(section).getAllByText('Plumbing');
    expect(plumbingA.className).toBe(plumbingB.className);
    expect(within(section).getByText('Electrical').className).not.toBe(plumbingA.className);
  });

  it('says what an empty queue means rather than showing nothing', async () => {
    serve({ triage: EMPTY_TRIAGE });
    renderLanding();

    expect(await screen.findByText(/Nothing new is waiting/)).toBeVisible();
    expect(screen.getByText(/You have not taken anything up/)).toBeVisible();
    expect(screen.getByText(/Nothing is waiting on a worker/)).toBeVisible();
    expect(screen.getByText(/Nobody is booked on anything/)).toBeVisible();
    expect(screen.getByText(/Nothing is under way this minute/)).toBeVisible();
  });
});

describe('sections 2 to 5 — rendered as the server bucketed them', () => {
  it('keeps a High complaint in "Taken up" instead of lifting it into the urgent stack', async () => {
    serve();
    renderLanding();

    const takenUp = await sectionFor('Taken up by you');
    await waitFor(() => expect(within(takenUp).getByText('Lift making a noise')).toBeVisible());

    // The row the browser would have got wrong if it re-bucketed: it is High,
    // and section 1 must not contain it.
    expect(within(await sectionFor('New complaints')).queryByText('Lift making a noise'))
      .not.toBeInTheDocument();
    expect(within(takenUp).getByText('In Progress')).toBeVisible();
  });

  it('shows the work orders of sections 4 and 5 under their own headers', async () => {
    serve();
    renderLanding();

    const assigned = await sectionFor('Assigned, work pending');
    await waitFor(() => expect(within(assigned).getByText('Water tank overflow')).toBeVisible());
    expect(within(assigned).getByText('Booked')).toBeVisible();

    const underWay = await sectionFor('Being worked right now');
    expect(within(underWay).getByText('Pump room flooding')).toBeVisible();
    expect(within(underWay).getByText('Under way')).toBeVisible();

    // Neither work order leaks into the complaint sections above.
    expect(within(await sectionFor('New complaints')).queryByText('Water tank overflow'))
      .not.toBeInTheDocument();
    expect(within(assigned).queryByText('Pump room flooding')).not.toBeInTheDocument();
  });

  it('leaves an offered-but-unaccepted job in "Open job requests", and names who was asked', async () => {
    serve();
    renderLanding();

    const open = await sectionFor('Open job requests');
    await waitFor(() => expect(within(open).getByText('Gate motor jammed')).toBeVisible());

    // Ruling A3 in one assertion: the server put an `offered` job here and the
    // browser does not promote it to "assigned" because somebody was asked.
    expect(within(open).getByText(/Offered to Meena Rao, awaiting acceptance/)).toBeVisible();
    expect(within(await sectionFor('Assigned, work pending')).queryByText('Gate motor jammed'))
      .not.toBeInTheDocument();
  });

  it('badges work inherited from somebody who left', async () => {
    serve();
    renderLanding();

    const assigned = await sectionFor('Assigned, work pending');
    await waitFor(() => expect(within(assigned).getByText('Water tank overflow')).toBeVisible());
    expect(within(assigned).getByText('Inherited')).toBeVisible();

    // Only where the server stamped it.
    expect(within(await sectionFor('Being worked right now')).queryByText('Inherited'))
      .not.toBeInTheDocument();
  });

  it('counts the time a job has been under way from the server’s startedAt', async () => {
    serve();
    renderLanding();

    const underWay = await sectionFor('Being worked right now');
    await waitFor(() => expect(within(underWay).getByText('Pump room flooding')).toBeVisible());
    expect(within(underWay).getByText(/under way 1h 35m/)).toBeVisible();
  });
});

describe('the three universal actions', () => {
  it('puts all three on every card in every section', async () => {
    serve();
    renderLanding();

    await screen.findByText('Sewage backing up');
    // Five sections, eight rows in the fixture, and not one of them is a card
    // you can only look at: the monitor-only sections carry the trio too.
    const cards = document.querySelectorAll('article');
    expect(cards).toHaveLength(8);
    for (const card of cards) {
      expect(within(card).getByRole('button', { name: /^View details of/ })).toBeEnabled();
      expect(within(card).getByRole('button', { name: /^Chat about/ })).toBeEnabled();
      expect(within(card).getByRole('button', { name: /^Add an internal note to/ })).toBeEnabled();
    }
  });

  it('opens a complaint’s chat thread and hands the id to the dock', async () => {
    const user = userEvent.setup();
    const opened = [];
    const listener = (event) => opened.push(event.detail);
    window.addEventListener('hb:chat-open', listener);
    serve();
    renderLanding();

    const underWay = await sectionFor('Being worked right now');
    await waitFor(() => expect(within(underWay).getByText('Pump room flooding')).toBeVisible());
    const card = within(underWay).getByText('Pump room flooding').closest('article');

    await user.click(within(card).getByRole('button', { name: /^Chat about/ }));

    // The work-order card carries `complaintId`, which is what the chat is
    // about — the thread is the complaint's, not the job's.
    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-under-way/chat', {
        method: 'POST', body: '{}',
      }));
    await waitFor(() => expect(opened).toEqual([{ threadId: 'thread-9' }]));
    window.removeEventListener('hb:chat-open', listener);
  });

  it('writes an internal note, and says who can read it', async () => {
    const user = userEvent.setup();
    serve();
    renderLanding();

    const section = await sectionFor('New complaints');
    await waitFor(() => expect(within(section).getByText('Sewage backing up')).toBeVisible());
    const card = within(section).getByText('Sewage backing up').closest('article');

    await user.click(within(card).getByRole('button', { name: /^Add an internal note to/ }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/The resident\s+does not/)).toBeVisible();

    // Empty is not a note.
    expect(within(dialog).getByRole('button', { name: 'Save note' })).toBeDisabled();
    await user.type(within(dialog).getByRole('textbox'), 'Riser is the real problem.');
    await user.click(within(dialog).getByRole('button', { name: 'Save note' }));

    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-urgent/notes', {
        method: 'POST',
        body: JSON.stringify({ note: 'Riser is the real problem.' }),
      }));
  });

  it('opens the eye popup with the stage’s own buttons inside it', async () => {
    const user = userEvent.setup();
    serve();
    renderLanding();

    const section = await sectionFor('New complaints');
    await waitFor(() => expect(within(section).getByText('Sewage backing up')).toBeVisible());
    const card = within(section).getByText('Sewage backing up').closest('article');

    await user.click(within(card).getByRole('button', { name: /^View details of/ }));

    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText(/come up through the basement drain/)).toBeVisible();
    expect(within(dialog).getByText(/Stage · New complaint/)).toBeVisible();
    // The stage's primary action, repeated where the reader now is.
    await user.click(within(dialog).getByRole('button', { name: /Take up/ }));
    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-urgent/take-up', {
        method: 'POST', body: '{}',
      }));
  });
});

describe('section 2 — taken up by you', () => {
  it('deep-links Raise job request into this portal’s work-order queue', async () => {
    serve();
    renderLanding();

    const takenUp = await sectionFor('Taken up by you');
    await waitFor(() => expect(within(takenUp).getByText('Lift making a noise')).toBeVisible());

    // The established mechanism (ruling A6), and portal-relative: a supervisor
    // who followed a `/admin` link here would land on a 403.
    expect(within(takenUp).getByRole('link', { name: /Raise job request/ }))
      .toHaveAttribute(
        'href',
        '/worker/departments/department-1/work-orders?tab=raise&complaint=complaint-mine',
      );
  });

  it('asks before resolving, then posts', async () => {
    const user = userEvent.setup();
    serve();
    renderLanding();

    const takenUp = await sectionFor('Taken up by you');
    await waitFor(() => expect(within(takenUp).getByText('Lift making a noise')).toBeVisible());
    const card = within(takenUp).getByText('Lift making a noise').closest('article');

    await user.click(within(card).getByRole('button', { name: 'Resolved' }));
    // Resolving cancels every unstarted job on the complaint and tells the
    // workers holding them. One click is not enough for that.
    expect(within(card).getByText(/Unstarted jobs on it are called off/)).toBeVisible();
    expect(mocks.api).not.toHaveBeenCalledWith(
      '/complaints/complaint-mine/resolve', expect.anything(),
    );

    await user.click(within(card).getByRole('button', { name: /Yes, resolve it/ }));
    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-mine/resolve', {
        method: 'POST', body: '{}',
      }));
  });

  it('shows the running-job refusal verbatim, on the card it refused', async () => {
    const user = userEvent.setup();
    serve({
      write: (path) => (path.endsWith('/resolve')
        ? Promise.reject(
          Object.assign(new Error('Finish or cancel the running job first.'), {
            status: 409, code: 'complaint_has_running_job', details: null,
          }),
        )
        : null),
    });
    renderLanding();

    const takenUp = await sectionFor('Taken up by you');
    await waitFor(() => expect(within(takenUp).getByText('Lift making a noise')).toBeVisible());
    const card = within(takenUp).getByText('Lift making a noise').closest('article');

    await user.click(within(card).getByRole('button', { name: 'Resolved' }));
    await user.click(within(card).getByRole('button', { name: /Yes, resolve it/ }));

    // Verbatim: the server names the condition, and a paraphrase would be this
    // screen guessing which of the complaint's jobs is running.
    expect(await within(card).findByRole('alert'))
      .toHaveTextContent('Finish or cancel the running job first.');
  });
});

describe('section 3 — open job requests', () => {
  it('raises the priority one step, and refuses to pretend there is a step above High', async () => {
    const user = userEvent.setup();
    serve();
    renderLanding();

    const open = await sectionFor('Open job requests');
    await waitFor(() => expect(within(open).getByText('Gate motor jammed')).toBeVisible());

    const medium = within(open).getByText('Gate motor jammed').closest('article');
    const raise = within(medium).getByRole('button', { name: /Raise priority to High/ });
    await user.click(raise);
    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-open/priority-raise', {
        method: 'POST', body: '{}',
      }));

    // At the top of the scale the button stays — disabled, and saying why.
    const high = within(open).getByText('Basement pump dead').closest('article');
    const blocked = within(high).getByRole('button', { name: /Already High/ });
    expect(blocked).toBeDisabled();
    expect(blocked).toHaveAttribute('title', expect.stringContaining('already High'));
  });

  it('calls the manual assign what it is, and force-assigns', async () => {
    const user = userEvent.setup();
    serve();
    renderLanding();

    const open = await sectionFor('Open job requests');
    await waitFor(() => expect(within(open).getByText('Gate motor jammed')).toBeVisible());
    const card = within(open).getByText('Gate motor jammed').closest('article');

    // Not "Offer" — the worker cannot decline this, and the button says so
    // before it is pressed (ruling A4).
    await user.click(within(card).getByRole('button', { name: 'Assign without asking' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/cannot decline it/)).toBeVisible();
    await user.click(await within(dialog).findByRole('button', { name: /Meena Rao/ }));
    await user.click(within(dialog).getByRole('button', { name: /they cannot decline/ }));

    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/work-orders/work-order-3/assign', {
        method: 'POST',
        body: JSON.stringify({ staffAssignmentId: 'staff-9', force: true }),
      }));
  });

  it('leaves the two monitor-only sections monitor-only', async () => {
    serve();
    renderLanding();

    const assigned = await sectionFor('Assigned, work pending');
    await waitFor(() => expect(within(assigned).getByText('Water tank overflow')).toBeVisible());

    for (const section of [assigned, await sectionFor('Being worked right now')]) {
      for (const verb of [/Assign without asking/, /Raise priority/, /Resolved/, /Take up/]) {
        expect(within(section).queryByRole('button', { name: verb })).not.toBeInTheDocument();
      }
    }
  });
});

describe('taking a complaint up', () => {
  it('posts to the complaint the button belongs to, and re-reads the department', async () => {
    const user = userEvent.setup();
    serve();
    renderLanding();

    const section = await sectionFor('New complaints');
    await waitFor(() => expect(within(section).getByText('Sewage backing up')).toBeVisible());

    const card = within(section).getByText('Sewage backing up').closest('article');
    const before = triageCalls().length;
    await user.click(within(card).getByRole('button', { name: /Take up/ }));

    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-urgent/take-up', {
        method: 'POST',
        body: '{}',
      }));
    // Which section the complaint lands in next is the server's answer, so the
    // success path re-reads instead of moving the card locally.
    await waitFor(() => expect(triageCalls().length).toBeGreaterThan(before));
  });

  it('puts a refusal on the card it was refused for, and leaves the others alone', async () => {
    const user = userEvent.setup();
    serve({
      write: (path) => (path.endsWith('/take-up')
        ? Promise.reject(
          Object.assign(new Error('Ravi Kumar took this up first.'), {
            status: 409, code: 'complaint_already_taken_up', details: null,
          }),
        )
        : null),
    });
    renderLanding();

    const section = await sectionFor('New complaints');
    await waitFor(() => expect(within(section).getByText('Sewage backing up')).toBeVisible());

    const card = within(section).getByText('Sewage backing up').closest('article');
    await user.click(within(card).getByRole('button', { name: /Take up/ }));

    expect(await within(card).findByRole('alert')).toHaveTextContent('Ravi Kumar took this up first.');
    const other = within(section).getByText('Corridor light flickering').closest('article');
    expect(within(other).queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('staying current', () => {
  it('refetches when the SSE beat fires the dashboard-refresh event', async () => {
    serve();
    renderLanding();

    await screen.findByText('Sewage backing up');
    const before = triageCalls().length;

    act(() => {
      window.dispatchEvent(new CustomEvent('homebandhu:dashboard-refresh'));
    });

    await waitFor(() => expect(triageCalls().length).toBeGreaterThan(before));
  });

  it('says so plainly when the department read fails, and offers a retry', async () => {
    const user = userEvent.setup();
    let attempt = 0;
    serve({
      triage: () => {
        attempt += 1;
        return attempt === 1
          ? Promise.reject(Object.assign(new Error('Not Found'), { status: 404 }))
          : Promise.resolve(TRIAGE);
      },
    });
    renderLanding();

    // This is the live shape until the migration is hand-applied: the endpoint
    // is not there, and the page has to say so rather than render four empty
    // sections that look like a quiet department.
    expect(await screen.findByRole('alert')).toHaveTextContent('Not Found');
    expect(screen.queryByRole('heading', { name: /New complaints/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Sewage backing up')).toBeVisible();
  });
});
