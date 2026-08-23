import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DepartmentHiring from './DepartmentHiring';

// The removal confirmation sheet (product ruling 4, 2026-08-21).
//
// What it replaced is why these tests exist. Both roster verbs used to be a
// `window.prompt`: the prompt asked for a reason and, by being the only thing in
// the way, doubled as the confirmation. So Remove + Enter took somebody off a
// roster having said nothing about what they held — and `window.prompt` is not
// implemented in jsdom at all, which is the other half of why this screen had no
// test until now.
//
// Four properties are pinned:
//
//   * the three-state button logic is unchanged (pending departure → Open
//     handover, booked items → Start handover, else Remove). The sheet is a
//     confirm layer, not a redesign, and a test that only covered the sheet
//     would let the states drift underneath it;
//   * the counts on it are the ones the API returned, not zeroes and not a
//     browser's arithmetic;
//   * the last-supervisor warning appears exactly when it is true;
//   * Cancel writes nothing. This is the property a prompt could not have — its
//     Cancel returned null and the caller had to remember to check.

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  state: {},
}));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));
vi.mock('../../store/useApp', () => ({ useApp: () => mocks.state }));

const staff = (overrides = {}) => ({
  id: 'staff-1',
  name: 'Ravi Kumar',
  phone: null,
  role: 'Plumber',
  rank: 'member',
  shift: null,
  status: 'active',
  membershipId: 'membership-1',
  serviceProviderId: null,
  supervisedWorkOrderCount: 0,
  openCommitmentCount: 0,
  departureStatus: null,
  departureEffectiveAt: null,
  ...overrides,
});

const department = (roster) => ({
  id: 'dept-1',
  name: 'Maintenance',
  description: '',
  categories: [],
  categoryIds: [],
  skills: [],
  skillIds: [],
  head: null,
  operatingHours: { start: '09:00', end: '18:00' },
  status: 'Active',
  canHire: true,
  staff: roster,
});

/**
 * Route every read this screen makes; only the roster read has content.
 *
 * `hiringApi.department` is the *list* endpoint filtered in the browser, not
 * `GET /departments/{id}` — see its own comment about which callers may use
 * which. Mocking the shape the screen actually asks for is the point.
 */
function serve(roster) {
  mocks.api.mockReset();
  mocks.api.mockImplementation((path) => {
    if (path.startsWith('/departments?')) {
      return Promise.resolve({ items: [department(roster)], total: 1 });
    }
    return Promise.resolve([]);
  });
}

beforeEach(() => {
  // `portal`, not a display role: `homeRouteFor` reads the key the backend
  // computed, and anything else lands the whole screen on `/account`.
  mocks.state = { currentUser: { portal: 'admin', departmentId: 'dept-1' } };
  serve([staff()]);
});

function renderRoster() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/admin/departments/dept-1/hiring?tab=roster']}>
        <Routes>
          <Route
            path="/admin/departments/:departmentId/hiring"
            element={<DepartmentHiring />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('the roster’s three verbs', () => {
  it('offers Remove when nothing is booked', async () => {
    renderRoster();
    expect(await screen.findByRole('button', { name: /Remove/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Start handover/ })).toBeNull();
  });

  it('offers Start handover instead while items are booked', async () => {
    serve([staff({ openCommitmentCount: 3 })]);
    renderRoster();
    expect(await screen.findByRole('button', { name: /Start handover/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /^Remove/ })).toBeNull();
  });

  it('offers neither to somebody already on their way out', async () => {
    serve([staff({ departureStatus: 'pending', openCommitmentCount: 2 })]);
    renderRoster();
    expect(await screen.findByRole('button', { name: /Open handover/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Start handover/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Remove/ })).toBeNull();
  });
});

describe('the confirmation sheet', () => {
  it('names the person and states both real counts', async () => {
    serve([
      staff({ rank: 'supervisor', supervisedWorkOrderCount: 4 }),
      staff({ id: 'staff-2', name: 'Asha Rao', rank: 'supervisor' }),
    ]);
    renderRoster();
    await userEvent.click((await screen.findAllByRole('button', { name: /^Remove/ }))[0]);

    const sheet = await screen.findByRole('dialog');
    expect(sheet.textContent).toContain('Ravi Kumar');
    expect(sheet.textContent).toContain('Supervisor');
    // Zero is said out loud rather than hidden: it is the fact that makes
    // Remove the safe button.
    expect(sheet.textContent).toContain('Nothing is booked in their name.');
    expect(sheet.textContent).toContain('4 live work orders they supervise');
  });

  it('warns when this is the department’s last supervisor', async () => {
    serve([staff({ rank: 'supervisor' }), staff({ id: 'staff-2', name: 'Asha Rao' })]);
    renderRoster();
    await userEvent.click((await screen.findAllByRole('button', { name: /^Remove/ }))[0]);

    expect(
      (await screen.findByRole('dialog')).textContent
    ).toContain('last supervisor');
  });

  it('does not warn while another supervisor remains', async () => {
    serve([
      staff({ rank: 'supervisor' }),
      staff({ id: 'staff-2', name: 'Asha Rao', rank: 'supervisor' }),
    ]);
    renderRoster();
    await userEvent.click((await screen.findAllByRole('button', { name: /^Remove/ }))[0]);

    expect((await screen.findByRole('dialog')).textContent).not.toContain(
      'last supervisor'
    );
  });

  it('does not warn about a member, however many are on the roster', async () => {
    renderRoster();
    await userEvent.click(await screen.findByRole('button', { name: /^Remove/ }));

    expect((await screen.findByRole('dialog')).textContent).not.toContain(
      'last supervisor'
    );
  });

  it('sends the reason with the removal when confirmed', async () => {
    renderRoster();
    await userEvent.click(await screen.findByRole('button', { name: /^Remove/ }));
    const sheet = await screen.findByRole('dialog');

    await userEvent.type(within(sheet).getByRole('textbox'), 'Moved cities');
    await userEvent.click(within(sheet).getByRole('button', { name: 'Remove' }));

    await waitFor(() =>
      expect(
        mocks.api.mock.calls.some(
          ([path, init]) =>
            path === '/departments/dept-1/members/staff-1/remove'
            && JSON.parse(init.body).reason === 'Moved cities'
        )
      ).toBe(true)
    );
  });

  it('writes nothing when it is cancelled', async () => {
    renderRoster();
    await userEvent.click(await screen.findByRole('button', { name: /^Remove/ }));
    const sheet = await screen.findByRole('dialog');
    await userEvent.click(within(sheet).getByRole('button', { name: 'Cancel' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(
      mocks.api.mock.calls.some(([, init]) => init?.method === 'POST')
    ).toBe(false);
  });

  it('opens a departure rather than a removal from the handover verb', async () => {
    serve([staff({ openCommitmentCount: 2 })]);
    renderRoster();
    await userEvent.click(await screen.findByRole('button', { name: /Start handover/ }));
    const sheet = await screen.findByRole('dialog');
    await userEvent.click(within(sheet).getByRole('button', { name: 'Start handover' }));

    await waitFor(() =>
      expect(
        mocks.api.mock.calls.some(
          ([path, init]) =>
            path === '/departments/dept-1/departures' && init?.method === 'POST'
        )
      ).toBe(true)
    );
    expect(
      mocks.api.mock.calls.some(([path]) => path.endsWith('/remove'))
    ).toBe(false);
  });
});

describe('the roster’s counts', () => {
  it('renders supervised work rather than the dead complaint count', async () => {
    serve([staff({ rank: 'supervisor', supervisedWorkOrderCount: 2 })]);
    renderRoster();

    expect(await screen.findByText(/2 supervised/)).toBeTruthy();
    // The number that was always zero, gone rather than repurposed in place.
    expect(screen.queryByText(/open complaints/)).toBeNull();
  });

  it('says nothing about supervised work for somebody who supervises none', async () => {
    renderRoster();
    await screen.findByRole('button', { name: /^Remove/ });
    expect(screen.queryByText(/supervised/)).toBeNull();
  });
});
