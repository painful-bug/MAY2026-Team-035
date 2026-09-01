import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Departments from './Departments';

// Round 1 pinned the blank screen (the `useQuery` import this page renders
// with). Round 2 pins the create-flow rework:
// - one generation of manager entry — the legacy free-text "Department
//   Manager" input is gone, `head` is derived from the first manager-ranked
//   invitation (and an edit without re-entered leaders preserves the old one);
// - the modal portals to document.body (an ancestor's `animate-fade-in`
//   fill-forwards opacity animation made <main> a permanent stacking context,
//   trapping z-[999] under the sticky header's z-40) and anchors items-start
//   so the title can never be clipped;
// - the category validation only appears after the field is touched or a
//   submit is attempted, never on a freshly opened form.

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  state: {},
}));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));

vi.mock('../../store/useApp', () => ({
  useApp: (selector) => (selector ? selector(mocks.state) : mocks.state),
}));

// No `departments` in the store state: the page reads the real
// `GET /departments` envelope now, and a store copy here would only let a
// test pass against a data path the page no longer has.
const baseState = () => ({
  complaints: [],
  createDepartment: vi.fn().mockResolvedValue({ id: 'dept-1' }),
  updateDepartment: vi.fn().mockResolvedValue({ id: 'dept-1' }),
  setDepartmentStatus: vi.fn(),
  deleteDepartment: vi.fn(),
});

const existingDepartment = () => ({
  id: 'dept-1',
  name: 'Maintenance',
  description: 'Fixes things',
  categories: ['Plumbing'],
  categoryIds: ['cat-1'],
  skills: [],
  skillIds: [],
  head: 'Old Head',
  email: 'maint@example.com',
  phone: '+91 90000 00000',
  operatingHours: { start: '09:00', end: '18:00' },
  slaHours: 24,
  status: 'Active',
  staff: [],
});

beforeEach(() => {
  // `/complaint-categories` for the tile and the category picker, `/skills`
  // for the skill picker — an empty community answers all of them with [].
  mocks.api.mockReset().mockResolvedValue([]);
  mocks.state = baseState();
});

function renderAt(url) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <Departments />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const submitButton = () =>
  screen
    .getAllByRole('button', { name: /create department/i })
    .find((button) => button.getAttribute('type') === 'submit');

const addCategory = async (user, name) => {
  const combobox = screen.getByRole('combobox', {
    name: /complaint categories/i,
  });
  await user.type(combobox, name);
  await user.click(
    await screen.findByRole('button', { name: /as a new category/i })
  );
};

describe('admin departments page', () => {
  it('renders the list view without crashing', async () => {
    renderAt('/admin/departments');

    expect(
      screen.getByRole('heading', { name: 'Departments' })
    ).toBeInTheDocument();
    // The list is fetched, so first paint says "Loading the departments…" and
    // the empty state arrives with the (empty) response.
    expect(
      await screen.findByText('Create your first department')
    ).toBeInTheDocument();
  });

  it('opens the create form when arriving with ?create=1', async () => {
    renderAt('/admin/departments?create=1');

    expect(
      await screen.findByRole('heading', { name: 'Create Department' })
    ).toBeInTheDocument();
    expect(screen.getByText('Department name')).toBeInTheDocument();
  });
});

describe('manager entry (single generation)', () => {
  it('has no legacy free-text manager field, only relabelled department contacts', async () => {
    renderAt('/admin/departments?create=1');
    await screen.findByRole('heading', { name: 'Create Department' });

    expect(screen.queryByText('Department manager')).not.toBeInTheDocument();
    expect(screen.getByText('Department contact email')).toBeInTheDocument();
    expect(screen.getByText('Department contact phone')).toBeInTheDocument();
    // The invitation block remains the one place a manager is entered.
    expect(screen.getByText('Manager and supervisors')).toBeInTheDocument();
  });

  it('derives head from the first manager invitation at submit time', async () => {
    const user = userEvent.setup();
    renderAt('/admin/departments?create=1');
    await screen.findByRole('heading', { name: 'Create Department' });

    await user.type(
      screen.getByPlaceholderText('e.g. Electrical Services'),
      'Plumbing Services'
    );
    await addCategory(user, 'Plumbing');
    // Create mode opens with one empty manager row.
    await user.type(screen.getByPlaceholderText('Full name'), 'Priya Sharma');
    await user.type(
      screen.getByPlaceholderText('Email for sign-in'),
      'priya@example.com'
    );
    await user.click(submitButton());

    await waitFor(() =>
      expect(mocks.state.createDepartment).toHaveBeenCalledWith(
        expect.objectContaining({
          head: 'Priya Sharma',
          categories: ['Plumbing'],
        })
      )
    );
  });

  it('preserves the existing head when editing without re-entering a manager', async () => {
    const user = userEvent.setup();
    // The department arrives through the real `GET /departments` envelope —
    // the repointing away from the store copy IS the persistence fix this
    // test exercises, so the fixture must feed the same door the page uses.
    mocks.api.mockImplementation((path) =>
      path.startsWith('/departments?')
        ? Promise.resolve({ items: [existingDepartment()] })
        : Promise.resolve([])
    );
    renderAt('/admin/departments');

    await user.click(
      await screen.findByRole('button', { name: 'Edit Maintenance' })
    );
    await screen.findByRole('heading', { name: 'Edit Department' });
    // Edit mode starts with no leader rows — leadership already invited is
    // not re-entered — and that absence must not blank the stored head.
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() =>
      expect(mocks.state.updateDepartment).toHaveBeenCalledWith(
        'dept-1',
        expect.objectContaining({ head: 'Old Head' })
      )
    );
  });
});

// Owner-approved product ruling (2026-08-30): `isSecurityDepartment` (the same
// heuristic the phone-required note already uses, just below the invitation
// block) now also decides the `kind` sent to `createDepartment` /
// `updateDepartment`, so an admin-created security department actually stores
// `kind = 'security'` instead of NULL.
describe('department kind', () => {
  it('sends kind: "security" for a department whose name matches the heuristic', async () => {
    const user = userEvent.setup();
    renderAt('/admin/departments?create=1');
    await screen.findByRole('heading', { name: 'Create Department' });

    await user.type(
      screen.getByPlaceholderText('e.g. Electrical Services'),
      'Security Services'
    );
    await addCategory(user, 'Patrol');
    // Same heuristic as the phone-required note just below the invitation
    // block, so filling the now-required phone in is what a real operator
    // would have to do here too.
    await user.type(screen.getByPlaceholderText('+91 98765 43210'), '+91 90000 00001');

    await user.click(submitButton());

    await waitFor(() =>
      expect(mocks.state.createDepartment).toHaveBeenCalledWith(
        expect.objectContaining({ kind: 'security' })
      )
    );
  });

  it('sends no kind for a department that does not match the heuristic', async () => {
    const user = userEvent.setup();
    renderAt('/admin/departments?create=1');
    await screen.findByRole('heading', { name: 'Create Department' });

    await user.type(
      screen.getByPlaceholderText('e.g. Electrical Services'),
      'Plumbing Services'
    );
    await addCategory(user, 'Plumbing');
    await user.click(submitButton());

    await waitFor(() =>
      expect(mocks.state.createDepartment).toHaveBeenCalledWith(
        expect.objectContaining({ kind: null })
      )
    );
  });
});

describe('category validation timing', () => {
  it('shows no error on a freshly opened form', async () => {
    renderAt('/admin/departments?create=1');
    await screen.findByRole('heading', { name: 'Create Department' });

    expect(
      screen.queryByText('Select at least one complaint category.')
    ).not.toBeInTheDocument();
  });

  it('shows the error once the field was touched and emptied again', async () => {
    const user = userEvent.setup();
    renderAt('/admin/departments?create=1');
    await screen.findByRole('heading', { name: 'Create Department' });

    await addCategory(user, 'Plumbing');
    expect(
      screen.queryByText('Select at least one complaint category.')
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Remove Plumbing' }));
    expect(
      screen.getByText('Select at least one complaint category.')
    ).toBeInTheDocument();
  });
});

describe('modal stacking and scroll', () => {
  it('portals the dialog to document.body with a top-anchored, full-cover overlay', async () => {
    renderAt('/admin/departments?create=1');
    const dialog = await screen.findByRole('dialog', {
      name: 'Create department',
    });

    // Portal: rendered under <body>, outside the layout's stacking context
    // (`animate-fade-in` keeps <main> a stacking context via its
    // fill-forwards opacity animation, which is what put the sticky header
    // above z-[999]).
    expect(dialog.parentElement).toBe(document.body);
    // Full-viewport overlay above the header, top-anchored so a tall panel
    // clips at the bottom into its own scrollbar, never at the title.
    expect(dialog.className).toContain('fixed inset-0');
    expect(dialog.className).toContain('z-[999]');
    expect(dialog.className).toContain('items-start');
    const panel = dialog.firstElementChild;
    expect(panel.className).toContain('overflow-y-auto');
    expect(panel.className).toContain('max-h-[calc(100vh-4rem)]');
  });
});
