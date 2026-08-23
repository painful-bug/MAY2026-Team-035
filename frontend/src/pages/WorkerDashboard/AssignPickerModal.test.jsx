import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AssignPickerModal from './AssignPickerModal';

// The force-assign picker.
//
// **The thing worth testing here is the honesty**, not the plumbing. Ruling A4
// gave the supervisor an override of the consent model: the worker cannot
// decline, and the difference between this and the work-order queue's *offer*
// is invisible in the request body — one boolean — and total for the person on
// the other end of it. So these tests pin the words on the screen as hard as
// they pin the `force: true`.

const mocks = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock('../../lib/api/client', () => ({ api: mocks.api }));

const ORDER = {
  id: 'work-order-3',
  complaintId: 'complaint-open',
  complaintTitle: 'Gate motor jammed',
  skillName: 'Electrician',
  scheduledStartAt: '2026-08-23T04:00:00.000Z',
};

const CANDIDATES = [
  { staffAssignmentId: 'staff-9', displayName: 'Meena Rao', openJobs: 2, excluded: false },
  {
    staffAssignmentId: 'staff-10',
    displayName: 'Anil Sharma',
    openJobs: 0,
    excluded: true,
    awayUntil: '2026-08-25T04:00:00.000Z',
  },
];

function serve({ candidates = CANDIDATES, assign } = {}) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path, options) => {
    if (path.startsWith('/work-orders/work-order-3/candidates')) {
      return typeof candidates === 'function' ? candidates() : Promise.resolve(candidates);
    }
    if (path === '/work-orders/work-order-3/assign' && options?.method === 'POST') {
      return assign ? assign() : Promise.resolve({ message: 'Assigned.' });
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
}

function renderPicker(props = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AssignPickerModal order={ORDER} onClose={() => {}} {...props} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.api.mockReset();
});

describe('assigning a job outright', () => {
  it('says plainly that this is not an offer', async () => {
    serve();
    renderPicker();

    expect(screen.getByText(/This is not an offer/)).toBeVisible();
    expect(screen.getByText(/cannot decline it/)).toBeVisible();
    // The other route is named, so a supervisor who wanted the ordinary one
    // knows where it is instead of pressing this and finding out.
    expect(screen.getByText(/offer the job from the work-order queue instead/)).toBeVisible();
  });

  it('lists the ranked candidates, including whoever declined this job earlier', async () => {
    serve();
    renderPicker();

    expect(await screen.findByRole('button', { name: /Meena Rao/ })).toBeVisible();
    // Shown rather than hidden: on a forced assignment, "has already said no to
    // this job" is context for the decision, not a reason to remove the name.
    expect(screen.getByRole('button', { name: /Anil Sharma/ })).toHaveTextContent(
      /declined this job earlier/,
    );
  });

  it('sends force, and nothing else it was not asked for', async () => {
    const user = userEvent.setup();
    serve();
    renderPicker();

    // Nobody picked: the button cannot fire.
    expect(screen.getByRole('button', { name: 'Assign without asking' })).toBeDisabled();

    await user.click(await screen.findByRole('button', { name: /Meena Rao/ }));
    const confirm = screen.getByRole('button', { name: /Assign Meena Rao — they cannot decline/ });
    await user.click(confirm);

    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/work-orders/work-order-3/assign', {
        method: 'POST',
        body: JSON.stringify({ staffAssignmentId: 'staff-9', force: true }),
      }));
  });

  it('closes on success, because the card behind it is about to move sections', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    serve();
    renderPicker({ onClose });

    await user.click(await screen.findByRole('button', { name: /Meena Rao/ }));
    await user.click(screen.getByRole('button', { name: /they cannot decline/ }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('keeps the picker open and shows the refusal when the database says no', async () => {
    const user = userEvent.setup();
    serve({
      assign: () => Promise.reject(
        Object.assign(new Error('Schedule this job before assigning it.'), { status: 409 }),
      ),
    });
    renderPicker();

    await user.click(await screen.findByRole('button', { name: /Meena Rao/ }));
    await user.click(screen.getByRole('button', { name: /they cannot decline/ }));

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('Schedule this job before assigning it.');
    // Still on the picker, with the choice still made: a refusal that closed
    // the modal would send the supervisor back to the card to start again.
    expect(screen.getByText('Meena Rao').closest('button'))
      .toHaveAttribute('aria-pressed', 'true');
  });

  it('says what an empty roster means instead of showing a picker with nothing in it', async () => {
    serve({ candidates: [] });
    renderPicker();

    // The empty list has several causes the server does not distinguish —
    // trade, leave, clashing bookings — so the copy must not pick one.
    expect(await screen.findByText(/Nobody on this department's roster is eligible/)).toBeVisible();
    expect(screen.getByText(/lack the trade, be on leave, or already be booked/)).toBeVisible();
  });

  it('explains the missing hour instead of asking a question whose answer is fixed', async () => {
    serve();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <AssignPickerModal order={{ ...ORDER, scheduledStartAt: null }} onClose={() => {}} />
      </QueryClientProvider>,
    );

    // `dispatch_candidates` structurally returns nobody for an unscheduled
    // job, so an empty roster here used to read as "nobody holds the trade" —
    // a wrong diagnosis. The screen now names the hour as the reason, points
    // at the queue, and never fetches the list at all.
    expect(screen.getByText(/no hour on it yet/)).toBeVisible();
    expect(screen.getByText(/Set a time in the work-order queue first/)).toBeVisible();
    expect(screen.queryByText(/Nobody on this department's roster/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Reading the roster/)).not.toBeInTheDocument();
    expect(mocks.api).not.toHaveBeenCalled();
  });
});
