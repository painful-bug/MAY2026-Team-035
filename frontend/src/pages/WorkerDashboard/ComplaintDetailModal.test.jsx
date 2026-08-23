import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ComplaintDetailModal from './ComplaintDetailModal';

// The eye popup, on its own.
//
// **The fixture is deliberately ugly**, because the wire is: `GET
// /complaints/staff/complaints/{id}` answers `to_jsonb(complaints_row)` and the
// raw `complaint_events` rows, so the keys are snake_case and the vocabulary is
// the *storage* one — `open`, not `Pending`; `high`, not `High`. Half the point
// of these tests is that the page renders that without the reader ever meeting
// a database word.
//
// The endpoint exists today (its guard widens from `require_admin` to active
// membership with this amendment); the note write behind the composer does not
// yet, which is why both are mocked.

const mocks = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock('../../lib/api/client', () => ({ api: mocks.api }));

const DETAIL = {
  complaint: {
    id: 'complaint-1',
    title: 'Sewage backing up',
    description: 'It has come up through the basement drain twice this week.',
    category: 'Plumbing',
    priority: 'high',
    status: 'acknowledged',
    location: 'Basement',
    created_at: '2026-08-22T05:00:00.000Z',
    expected_resolution_at: '2026-08-23T05:00:00.000Z',
    taken_up_at: '2026-08-22T06:00:00.000Z',
    returned_to_pool_at: '2026-08-21T05:00:00.000Z',
    reopened_count: 2,
  },
  events: [
    {
      id: 'event-1',
      event_type: 'raised',
      payload: {},
      created_at: '2026-08-22T05:00:00.000Z',
      message: 'The complaint was submitted to the management team.',
    },
    {
      id: 'event-2',
      event_type: 'note_added',
      payload: { note: 'Riser is the real problem.', internal: true },
      created_at: '2026-08-22T06:30:00.000Z',
      message: 'Riser is the real problem.',
      actor_name: 'Ravi Kumar',
    },
  ],
};

function serve({ detail = DETAIL, note } = {}) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path, options) => {
    if (path === '/complaints/staff/complaints/complaint-1' && !options) {
      return typeof detail === 'function' ? detail() : Promise.resolve(detail);
    }
    if (path === '/complaints/complaint-1/notes' && options?.method === 'POST') {
      return note ? note() : Promise.resolve({ message: 'Noted.' });
    }
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
}

function renderModal(props = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ComplaintDetailModal
        complaintId="complaint-1"
        fallback={{ title: 'Sewage backing up', subtitle: 'Asha Devi · B-402' }}
        stage="Taken up by you"
        onClose={() => {}}
        {...props}
      />
    </QueryClientProvider>,
  );
}

// Braces, not a concise arrow: `mockReset()` returns the mock, and a `beforeEach`
// that returns a function has handed vitest a teardown callback — which it then
// calls, as `api()` with no path.
beforeEach(() => {
  mocks.api.mockReset();
});

describe('the complaint detail popup', () => {
  it('renders the staff DTO without showing a database word', async () => {
    serve();
    renderModal();

    expect(await screen.findByText(/come up through the basement drain/)).toBeVisible();
    // Storage vocabulary in, wire vocabulary out.
    expect(screen.getByText('High')).toBeVisible();
    expect(screen.getByText('In Progress')).toBeVisible();
    expect(screen.queryByText('acknowledged')).not.toBeInTheDocument();
    expect(screen.getByText('Plumbing')).toBeVisible();
    // The same badges section 1 draws, from the same row's own columns.
    expect(screen.getByText('Returned to pool')).toBeVisible();
    expect(screen.getByText('Reopened ×2')).toBeVisible();
    expect(screen.getByText(/Stage · Taken up by you/)).toBeVisible();
  });

  it('shows the whole timeline, and marks what the resident cannot see', async () => {
    serve();
    renderModal();

    const note = (await screen.findByText('Riser is the real problem.')).closest('li');
    expect(within(note).getByText('Internal')).toBeVisible();
    expect(within(note).getByText(/Ravi Kumar/)).toBeVisible();
    // The other line is not marked: `note_added` without the payload flag is
    // the admin's resident-visible update, and this popup is not allowed to
    // relabel it.
    const raised = screen.getByText(/submitted to the management team/).closest('li');
    expect(within(raised).queryByText('Internal')).not.toBeInTheDocument();
  });

  it('repeats the stage’s own buttons inside the popup', async () => {
    serve();
    renderModal({ actions: <button type="button">Take up</button> });

    expect(await screen.findByRole('button', { name: 'Take up' })).toBeVisible();
    expect(screen.getByText(/What you can do from here/)).toBeVisible();
  });

  it('writes a note and re-reads the timeline it belongs on', async () => {
    const user = userEvent.setup();
    serve();
    renderModal();

    await screen.findByText(/come up through the basement drain/);
    const reads = () => mocks.api.mock.calls
      .filter(([path, options]) => path.startsWith('/complaints/staff/') && !options).length;
    const before = reads();

    await user.type(screen.getByRole('textbox'), 'Third call about this tap.');
    await user.click(screen.getByRole('button', { name: 'Save note' }));

    await waitFor(() =>
      expect(mocks.api).toHaveBeenCalledWith('/complaints/complaint-1/notes', {
        method: 'POST',
        body: JSON.stringify({ note: 'Third call about this tap.' }),
      }));
    // The note is now on the timeline behind the composer, so the detail is
    // read again rather than the browser appending its own copy of it.
    await waitFor(() => expect(reads()).toBeGreaterThan(before));
  });

  it('says a note was refused rather than clearing the box', async () => {
    const user = userEvent.setup();
    serve({
      note: () => Promise.reject(
        Object.assign(new Error('You do not supervise this department.'), { status: 403 }),
      ),
    });
    renderModal();

    await screen.findByText(/come up through the basement drain/);
    await user.type(screen.getByRole('textbox'), 'Something worth keeping.');
    await user.click(screen.getByRole('button', { name: 'Save note' }));

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('You do not supervise this department.');
    expect(screen.getByRole('textbox')).toHaveValue('Something worth keeping.');
  });

  it('shows the card’s own values while the read is in flight, and the failure if it fails', async () => {
    serve({
      detail: () => Promise.reject(Object.assign(new Error('Not Found'), { status: 404 })),
    });
    renderModal();

    // The header is the card's, so the popup never opens blank — and the body
    // is honest about the read that did not answer.
    expect(screen.getAllByText('Sewage backing up').length).toBeGreaterThan(0);
    expect(await screen.findByRole('alert')).toHaveTextContent('Not Found');
  });

  it('has a close control a keyboard and a screen reader can both find', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    serve();
    renderModal({ onClose });

    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalled();
  });
});
