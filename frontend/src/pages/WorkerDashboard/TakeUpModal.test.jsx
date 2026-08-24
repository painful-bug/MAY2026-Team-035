import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TakeUpModal from './TakeUpModal';

// The supervisor's take-up.
//
// **What is worth pinning here is the framing**, the same way the force-assign
// picker's tests pin its honesty. Ruling R1 took leadership out of every
// candidate flow — the picker, the board, the ping, the auto-book — and ruling
// R8 put this one door back beside them, deliberately outside the routine: *"it
// sholdnt be something seen in normal routine workflow"*. So these tests hold
// the banner that says so as hard as they hold the request, and they hold the
// request's **shape**: no `staffAssignmentId`, because the assignee is the
// caller and there is nobody else this button can reach.

const mocks = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock('../../lib/api/client', () => ({ api: mocks.api }));

const ORDER = {
  id: 'work-order-3',
  complaintId: 'complaint-open',
  complaintTitle: 'Gate motor jammed',
  complaintCategory: 'Electrical',
  skillName: 'Electrician',
  locationText: 'Main gate',
  scheduledStartAt: '2026-08-23T04:00:00.000Z',
  scheduledEndAt: '2026-08-23T05:00:00.000Z',
};

function serve({ takeUp } = {}) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path, options) => {
    if (path === '/work-orders/work-order-3/take-up' && options?.method === 'POST') {
      return takeUp ? takeUp() : Promise.resolve({ id: 'work-order-3', status: 'scheduled' });
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
}

function renderModal({ order = ORDER, ...props } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <TakeUpModal order={order} onClose={() => {}} {...props} />
    </QueryClientProvider>,
  );
  return queryClient;
}

const confirm = () => screen.getByRole('button', { name: /Take up this job — assign it to me/ });

beforeEach(() => {
  mocks.api.mockReset();
});

describe('a supervisor taking a job themselves', () => {
  it('names the norm it is stepping outside, in the banner', () => {
    serve();
    renderModal();

    // R8's exception framing. Not a warning about somebody else's consent —
    // nobody's is being overridden — but about the department this leaves
    // short-handed.
    expect(
      screen.getByText('Jobs normally go to your technicians — this assigns it to you.'),
    ).toBeVisible();
  });

  it('shows which job it is about to hand you, and when', () => {
    serve();
    renderModal();

    // Twice over: the shell's subtitle, and the summary that spells the job out
    // beside its trade, its place and its hour.
    expect(screen.getAllByText('Gate motor jammed')).toHaveLength(2);
    expect(screen.getByText('Electrician')).toBeVisible();
    expect(screen.getByText('Main gate')).toBeVisible();
    expect(screen.getByText(/Booked for/)).toBeVisible();
  });

  it('posts to the take-up endpoint with no assignee in the body', async () => {
    const user = userEvent.setup();
    serve();
    renderModal();

    await user.click(confirm());

    // The body is empty on purpose: `take_up_work_order` resolves the assignee
    // from `auth.uid()`, so there is no `staffAssignmentId` to send and this
    // button cannot be pointed at anybody else.
    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/work-orders/work-order-3/take-up', {
        method: 'POST',
        body: '{}',
      }));
  });

  it('closes on success, and re-reads both surfaces the job is on', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    serve();
    const queryClient = renderModal({ onClose });
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');

    await user.click(confirm());

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    // The job leaves "Open job requests" for "Assigned, work pending", and the
    // queue behind the dashboard holds it too. Which bucket it lands in is the
    // server's answer, so both are re-read rather than moved locally.
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['supervisor-triage'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['work-orders'] });
  });

  it('stays open and shows the refusal verbatim when the database says no', async () => {
    const user = userEvent.setup();
    serve({
      takeUp: () => Promise.reject(
        Object.assign(new Error('You are already booked over that hour.'), { status: 409 }),
      ),
    });
    const onClose = vi.fn();
    renderModal({ onClose });

    await user.click(confirm());

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('You are already booked over that hour.');
    // A refusal that closed the modal would send the supervisor back to the
    // card with no idea why nothing happened.
    expect(onClose).not.toHaveBeenCalled();
    expect(confirm()).toBeVisible();
  });

  it('surfaces the leadership refusal the same way', async () => {
    const user = userEvent.setup();
    serve({
      takeUp: () => Promise.reject(
        Object.assign(new Error('You do not lead this department.'), { status: 403 }),
      ),
    });
    renderModal();

    await user.click(confirm());

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('You do not lead this department.');
  });

  it('refuses an hourless job before the request rather than after it', async () => {
    serve();
    renderModal({ order: { ...ORDER, scheduledStartAt: null, scheduledEndAt: null } });

    // The overlap constraint is partial on `scheduled_start_at is not null`, so
    // a job with no hour cannot be assigned to anybody — the supervisor
    // included. Same sentence and same destination as the force-assign picker.
    expect(screen.getByText(/No time set yet/)).toBeVisible();
    expect(screen.getByText(/no hour on it yet/)).toBeVisible();
    expect(screen.getByText(/Set a time in the work-order queue first/)).toBeVisible();
    expect(confirm()).toBeDisabled();
    expect(mocks.api).not.toHaveBeenCalled();
  });
});
