import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import OpenJobs from './OpenJobs';

const mocks = vi.hoisted(() => ({
  snapshot: vi.fn(),
  openJobs: vi.fn(),
  claimJob: vi.fn(),
}));

vi.mock('../../features/worker/workerApi', () => ({
  workerApi: {
    snapshot: mocks.snapshot,
    openJobs: mocks.openJobs,
    claimJob: mocks.claimJob,
  },
}));

const engagement = {
  staffAssignmentId: 'staff-1',
  communityId: 'community-1',
  communityName: 'Green Meadows',
  departmentId: 'department-1',
  departmentName: 'Plumbing',
  rank: 'member',
  status: 'active',
};

const openJob = (overrides = {}) => ({
  workOrderId: 'work-order-1',
  complaintId: 'complaint-1',
  complaintTitle: 'Leaking tap',
  departmentId: 'department-1',
  departmentName: 'Plumbing',
  communityId: 'community-1',
  communityName: 'Green Meadows',
  skillId: 'skill-1',
  skillName: 'Plumbing',
  priority: 'medium',
  subjectKind: 'resident',
  scheduledStartAt: null,
  scheduledEndAt: null,
  createdAt: '2026-08-22T09:00:00Z',
  staffAssignmentId: 'staff-1',
  ...overrides,
});

function renderBoard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <OpenJobs />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.snapshot.mockReset().mockResolvedValue({ provider: null, communities: [engagement] });
  mocks.openJobs.mockReset().mockResolvedValue([openJob()]);
  mocks.claimJob.mockReset();
});

describe('OpenJobs', () => {
  it('draws the card from the board row, with Time to be set for a null slot', async () => {
    // Ruling C3: an unscheduled job is on the board with a marker, not hidden.
    // The marker is drawn from exactly the null the RPC passes through.
    renderBoard();

    expect(await screen.findByText('Leaking tap')).toBeVisible();
    expect(screen.getByText('Plumbing · Green Meadows')).toBeVisible();
    expect(screen.getByText('Time to be set')).toBeVisible();
    expect(screen.getByRole('button', { name: /claim this job/i })).toBeVisible();
  });

  it('marks a high-priority job urgent and prints a scheduled slot instead of the marker', async () => {
    mocks.openJobs.mockResolvedValue([
      openJob({
        priority: 'high',
        scheduledStartAt: '2026-08-24T09:00:00Z',
        scheduledEndAt: '2026-08-24T10:00:00Z',
      }),
    ]);
    renderBoard();

    expect(await screen.findByText('urgent')).toBeVisible();
    expect(screen.queryByText('Time to be set')).not.toBeInTheDocument();
  });

  it('claims in two steps, and the confirm wording says instant and supervisor-told', async () => {
    // Ruling C2: no approval step sits between the tap and the commitment, so
    // the confirm copy has to carry what the offer flow would have said.
    const user = userEvent.setup();
    mocks.claimJob.mockResolvedValue({ workOrderId: 'work-order-1', workOrderStatus: 'scheduled' });
    renderBoard();

    await user.click(await screen.findByRole('button', { name: /claim this job/i }));
    expect(mocks.claimJob).not.toHaveBeenCalled();
    expect(screen.getByText(/yours immediately/i)).toBeVisible();
    expect(screen.getByText(/the supervisor is told/i)).toBeVisible();

    await user.click(screen.getByRole('button', { name: /yes, it is mine/i }));
    await waitFor(() => expect(mocks.claimJob).toHaveBeenCalledWith('work-order-1'));
    // Both reads went stale the moment the claim returned: the job left the
    // board and landed on the dashboard.
    await waitFor(() => expect(mocks.openJobs.mock.calls.length).toBeGreaterThanOrEqual(2));
    await waitFor(() => expect(mocks.snapshot.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('backs out of the confirm step without claiming', async () => {
    const user = userEvent.setup();
    renderBoard();

    await user.click(await screen.findByRole('button', { name: /claim this job/i }));
    await user.click(screen.getByRole('button', { name: /not now/i }));

    expect(mocks.claimJob).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /claim this job/i })).toBeVisible();
  });

  it('prints the server sentence on the card and refreshes when the race is lost', async () => {
    // First come, first served means somebody loses, ordinarily. The server's
    // own words are the ones worth printing verbatim.
    const user = userEvent.setup();
    mocks.claimJob.mockRejectedValue(new Error('Somebody has already taken this job.'));
    renderBoard();

    await user.click(await screen.findByRole('button', { name: /claim this job/i }));
    await user.click(screen.getByRole('button', { name: /yes, it is mine/i }));

    expect(await screen.findByText('Somebody has already taken this job.')).toBeVisible();
    await waitFor(() => expect(mocks.openJobs.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('tells an unhired caller that jobs arrive with hiring', async () => {
    mocks.snapshot.mockResolvedValue({ provider: null, communities: [] });
    mocks.openJobs.mockResolvedValue([]);
    renderBoard();

    expect(
      await screen.findByText('Jobs appear here once a community hires you.'),
    ).toBeVisible();
  });

  it('tells a rostered caller with an empty board that nothing is waiting', async () => {
    mocks.openJobs.mockResolvedValue([]);
    renderBoard();

    expect(await screen.findByText('Nothing is waiting right now.')).toBeVisible();
  });

  it('surfaces a board read failure in its own words', async () => {
    mocks.openJobs.mockRejectedValue(new Error('Could not read the board.'));
    renderBoard();

    expect(await screen.findByText('Could not read the board.')).toBeVisible();
  });
});
