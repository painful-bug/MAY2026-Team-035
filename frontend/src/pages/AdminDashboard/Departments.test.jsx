import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Departments from './Departments';

// Regression tests for the 2026-08-12 blank screen: this page's "unassigned
// types" tile calls `useQuery`, and the import was missing — a ReferenceError
// on every render, which with no error boundary unmounted the entire app.
// Rendering the page at all (and at `?create=1`, the URL it was found on) is
// the assertion that matters.

const mocks = vi.hoisted(() => ({ api: vi.fn() }));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));

vi.mock('../../store/useApp', () => ({
  useApp: () => ({
    departments: [],
    complaints: [],
    createDepartment: vi.fn(),
    updateDepartment: vi.fn(),
    setDepartmentStatus: vi.fn(),
    deleteDepartment: vi.fn(),
  }),
}));

beforeEach(() => {
  // `/complaint-categories` for the tile and the category picker, `/skills`
  // for the skill picker — an empty community answers all of them with [].
  mocks.api.mockReset().mockResolvedValue([]);
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

    // The effect that reads `?create=1` opens the modal on mount.
    expect(
      await screen.findByRole('heading', { name: 'Create Department' })
    ).toBeInTheDocument();
    // The form itself is mounted — not just a heading.
    expect(screen.getByText('Department name')).toBeInTheDocument();
  });
});
