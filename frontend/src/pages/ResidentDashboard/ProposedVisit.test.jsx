import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProposedVisit } from './Complaints';

// The resident's visit card, and the two different questions it asks.
//
// **Why this is mocked at the HTTP boundary.** `POST /complaints/{id}/
// schedule-time` and the `mode` field on `GET /complaints/{id}/
// schedule-request` are not on the running backend yet — the migration behind
// ruling F1 is hand-applied by the owner. The frozen interface in
// `docs/plans/RESIDENT_SETS_THE_TIME_SPEC.md` is what these fixtures are
// written against, and these tests are the only thing holding the card to it
// until the endpoints land.
//
// What is pinned:
//
//   * `mode` is the discriminator, and a response without one still renders
//     the approve card exactly as it did before this feature existed. A card
//     that guessed "pick" from the missing times would flip every un-proposed
//     visit into a form the backend would refuse;
//   * pick-mode collects a start and an end, refuses an end that is not after
//     the start before the round trip, and sends `{ startAt, endAt }` as ISO;
//   * pick-mode has no decline (ruling F3);
//   * the server's `409` sentences reach the card verbatim, exactly as the
//     approve-mode answer's do.

const mocks = vi.hoisted(() => ({ api: vi.fn() }));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));

const PICK = {
  workOrderId: 'work-order-1',
  complaintId: 'complaint-1',
  mode: 'pick',
  status: 'awaiting_resident',
  awaitingResponse: true,
  scheduledStartAt: null,
  scheduledEndAt: null,
  respondBy: '2026-08-24T09:00:00.000Z',
  departmentName: 'Plumbing',
  skillName: 'Plumber',
  locationText: 'Flat B-402',
  assigneeName: null,
};

const APPROVE = {
  ...PICK,
  mode: 'approve',
  scheduledStartAt: '2026-08-25T04:30:00.000Z',
  scheduledEndAt: '2026-08-25T05:30:00.000Z',
};

/** Answer the card's one read, and whatever write it makes. */
function serve({ visit = PICK, write } = {}) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path, options) => {
    if (path === '/complaints/complaint-1/schedule-request' && !options) {
      return typeof visit === 'function' ? visit() : Promise.resolve(visit);
    }
    if (options?.method === 'POST') {
      if (write) {
        const answer = write(path, options);
        if (answer) return answer;
      }
      return Promise.resolve({ ...APPROVE, awaitingResponse: false, status: 'offered' });
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
}

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ProposedVisit complaintId="complaint-1" />
    </QueryClientProvider>,
  );
}

const picker = () => document.querySelectorAll('input[type="datetime-local"]');

beforeEach(() => {
  mocks.api.mockReset();
});

describe('pick-mode — the resident names the hour', () => {
  it('asks for a time instead of proposing one, and says what silence costs', async () => {
    serve();
    renderCard();

    expect(await screen.findByText('Pick a time for this visit')).toBeVisible();
    expect(picker()).toHaveLength(2);
    expect(screen.getByLabelText('Starts')).toBeRequired();
    expect(screen.getByLabelText('Ends')).toBeRequired();
    expect(
      screen.getByText(
        /If you have not picked a time within 24 hours, the association books the first available hour\./,
      ),
    ).toBeVisible();

    // Ruling F3: no decline. There is no proposal to send back.
    expect(screen.queryByRole('button', { name: 'It does not' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'That time works' })).not.toBeInTheDocument();
    // And nothing pretends a time was proposed.
    expect(screen.queryByText(/has not been proposed yet/)).not.toBeInTheDocument();
  });

  it('sends the two ends as ISO, on the endpoint the spec froze', async () => {
    const user = userEvent.setup();
    serve();
    renderCard();

    await screen.findByText('Pick a time for this visit');
    await user.type(screen.getByLabelText('Starts'), '2026-08-25T10:00');
    await user.type(screen.getByLabelText('Ends'), '2026-08-25T11:00');
    await user.click(screen.getByRole('button', { name: 'Set this time' }));

    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-1/schedule-time', {
        method: 'POST',
        // A `datetime-local` is local wall-clock with no zone; the card stamps
        // the browser's own zone on it rather than handing the server a naive
        // literal to guess at.
        body: JSON.stringify({
          startAt: new Date('2026-08-25T10:00').toISOString(),
          endAt: new Date('2026-08-25T11:00').toISOString(),
        }),
      }));
  });

  it('refuses an end that is not after the start, without asking the server', async () => {
    const user = userEvent.setup();
    serve();
    renderCard();

    await screen.findByText('Pick a time for this visit');
    await user.type(screen.getByLabelText('Starts'), '2026-08-25T11:00');
    await user.type(screen.getByLabelText('Ends'), '2026-08-25T10:00');

    expect(screen.getByText('The visit has to end after it starts.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Set this time' })).toBeDisabled();
    expect(mocks.api).not.toHaveBeenCalledWith(
      '/complaints/complaint-1/schedule-time',
      expect.anything(),
    );
  });

  it('prints the server’s refusal verbatim on the card', async () => {
    const user = userEvent.setup();
    serve({
      write: (path) => (path.endsWith('/schedule-time')
        ? Promise.reject(
          Object.assign(
            new Error('The association proposed this visit’s time — answer that instead.'),
            { status: 409, code: 'work_order_schedule_conflict', details: null },
          ),
        )
        : null),
    });
    renderCard();

    await screen.findByText('Pick a time for this visit');
    await user.type(screen.getByLabelText('Starts'), '2026-08-25T10:00');
    await user.type(screen.getByLabelText('Ends'), '2026-08-25T11:00');
    await user.click(screen.getByRole('button', { name: 'Set this time' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The association proposed this visit’s time — answer that instead.',
    );
  });
});

describe('approve-mode — unchanged by this feature', () => {
  it('still offers the two answers and draws no picker', async () => {
    serve({ visit: APPROVE });
    renderCard();

    expect(await screen.findByText('A visit has been proposed')).toBeVisible();
    expect(screen.getByRole('button', { name: 'That time works' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'It does not' })).toBeEnabled();
    expect(picker()).toHaveLength(0);
    expect(screen.queryByText('Pick a time for this visit')).not.toBeInTheDocument();
  });

  it('renders as approve when the backend sends no mode at all', async () => {
    // The live shape until the migration is hand-applied. A card that read
    // "no proposed time" as "you pick" would offer a form the server refuses.
    const { mode, ...withoutMode } = APPROVE;
    expect(mode).toBe('approve');
    serve({ visit: withoutMode });
    renderCard();

    expect(await screen.findByText('A visit has been proposed')).toBeVisible();
    expect(picker()).toHaveLength(0);
  });

  it('answers on the endpoint it always did', async () => {
    const user = userEvent.setup();
    serve({ visit: APPROVE });
    renderCard();

    await screen.findByText('A visit has been proposed');
    await user.click(screen.getByRole('button', { name: 'That time works' }));

    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-1/schedule', {
        method: 'POST',
        body: JSON.stringify({ response: 'confirmed', note: null }),
      }));
  });
});

describe('nothing to schedule', () => {
  it('draws no card at all on a 404', async () => {
    serve({
      visit: () => Promise.reject(Object.assign(new Error('Not Found'), { status: 404 })),
    });
    renderCard();

    // The ordinary case for most complaints, and not an error on screen.
    await waitFor(() => expect(mocks.api).toHaveBeenCalled());
    await waitFor(() => expect(document.querySelector('section')).toBeNull());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
