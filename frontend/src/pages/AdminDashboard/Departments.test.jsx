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

vi.mock('../../store/useApp', () => ({ useApp: () => mocks.state }));

const baseState = () => ({
  departments: [],
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
  it('renders the list view without crashing', () => {
    renderAt('/admin/departments');

    expect(
      screen.getByRole('heading', { name: 'Departments' })
    ).toBeInTheDocument();
    expect(screen.getByText('Create your first department')).toBeInTheDocument();
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
    mocks.state = { ...baseState(), departments: [existingDepartment()] };
    renderAt('/admin/departments');

    await user.click(screen.getByRole('button', { name: 'Edit Maintenance' }));
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
