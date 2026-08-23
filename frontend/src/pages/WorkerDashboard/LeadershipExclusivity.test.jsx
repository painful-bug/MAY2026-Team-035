import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';

// The two screens the leadership rulings of 2026-08-21 changed what is on.
//
// RULING 3 — "removal severs access completely" — is enforced in Postgres for
// everything the supervisor's portal reads except one thing: `communities[]` on
// the worker snapshot is composed in Python, and the Complaints screen picks a
// department out of it. So the screen's own choice is worth pinning: given an
// ended community-A engagement beside a live community-B one, it must open B.
// (The backend already refuses to return the ended row — see
// `backend/tests/test_leadership_stale_access.py`. This asserts the screen does
// not resurrect it if one ever arrives, which is the cheap half of defence in
// depth.)
//
// RULING 1 and 2 are refused at claim time, where nobody is watching. The
// pending-invitation list is where that answer surfaces, and before this it
// could only say "waiting for first sign-in" — which after a blocked claim is
// false.

const mocks = vi.hoisted(() => ({
  snapshot: vi.fn(),
  departmentComplaints: vi.fn(),
  changeRequests: vi.fn(),
  departmentOptions: vi.fn(),
  updateStaffInvitation: vi.fn(),
  revokeStaffInvitation: vi.fn(),
}));

vi.mock('../../features/worker/workerApi', () => ({
  workerApi: { snapshot: mocks.snapshot },
}));

vi.mock('../../features/complaints/routingApi', () => ({
  complaintRoutingApi: {
    departmentComplaints: mocks.departmentComplaints,
    changeRequests: mocks.changeRequests,
    departmentOptions: mocks.departmentOptions,
  },
}));

vi.mock('../../features/departments/departmentsApi', () => ({
  departmentsApi: {
    updateStaffInvitation: mocks.updateStaffInvitation,
    revokeStaffInvitation: mocks.revokeStaffInvitation,
  },
}));

const ENDED_IN_A = {
  staffAssignmentId: 'staff-a',
  communityId: 'community-a',
  communityName: 'Green Meadows',
  departmentId: 'department-a',
  departmentName: 'Plumbing',
  rank: 'supervisor',
  status: 'inactive',
};

const LIVE_IN_B = {
  staffAssignmentId: 'staff-b',
  communityId: 'community-b',
  communityName: 'Blue Waters',
  departmentId: 'department-b',
  departmentName: 'Electrical',
  rank: 'supervisor',
  status: 'active',
};

beforeEach(() => {
  for (const fn of Object.values(mocks)) fn.mockReset();
  mocks.departmentComplaints.mockResolvedValue([]);
  mocks.changeRequests.mockResolvedValue([]);
  mocks.departmentOptions.mockResolvedValue([]);
});

function renderWithQuery(ui) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

it('opens the community that still employs them, not the one they left', async () => {
  // The ended engagement is listed first on purpose: the screen takes the
  // *first* leadership row it finds, so an implementation that forgot the
  // status test would pick community A here and pass a test that only ever fed
  // it live rows.
  mocks.snapshot.mockResolvedValue({
    provider: null,
    communities: [ENDED_IN_A, LIVE_IN_B],
  });

  const { default: WorkerComplaints } = await import('./Complaints');
  renderWithQuery(<WorkerComplaints />);

  expect(await screen.findByText(/Electrical — Blue Waters/)).toBeInTheDocument();
  expect(screen.queryByText(/Plumbing — Green Meadows/)).not.toBeInTheDocument();
  expect(mocks.departmentComplaints).toHaveBeenCalledWith('department-b');
});

it('offers no complaints screen at all once every posting has ended', async () => {
  mocks.snapshot.mockResolvedValue({ provider: null, communities: [ENDED_IN_A] });

  const { default: WorkerComplaints } = await import('./Complaints');
  renderWithQuery(<WorkerComplaints />);

  expect(await screen.findByText(/Complaints are shown to supervisors/)).toBeInTheDocument();
  expect(mocks.departmentComplaints).not.toHaveBeenCalled();
});

it('tells the department why an invitee signed in and was turned away', async () => {
  const { default: PendingInvitations } = await import(
    '../../features/departments/components/PendingInvitations'
  );

  renderWithQuery(
    <PendingInvitations
      departmentId="department-b"
      invitations={[
        {
          id: 'invitation-id',
          name: 'Ravi Kumar',
          email: 'ravi@example.com',
          rank: 'supervisor',
          status: 'pending',
          blockedReason:
            'They signed in with an account that is registered as a marketplace service professional.',
        },
      ]}
    />,
  );

  expect(
    screen.getByText(/registered as a marketplace service professional/),
  ).toBeInTheDocument();
  // Still correctable and still withdrawable: the row stays pending because
  // the situation is not terminal.
  expect(
    screen.getByLabelText('Correct the invitation for Ravi Kumar'),
  ).toBeInTheDocument();
});

it('says nothing extra about an ordinary invitation still being waited on', async () => {
  const { default: PendingInvitations } = await import(
    '../../features/departments/components/PendingInvitations'
  );

  renderWithQuery(
    <PendingInvitations
      departmentId="department-b"
      invitations={[
        {
          id: 'invitation-id',
          name: 'Priya Nair',
          email: 'priya@example.com',
          rank: 'manager',
          status: 'pending',
          blockedReason: null,
        },
      ]}
    />,
  );

  expect(screen.getByText('priya@example.com')).toBeInTheDocument();
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
