import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DepartmentDetail from './DepartmentDetail';

// The "Assign to staff" control is gone (ruling R13, executed 2026-08-21).
//
// It wrote `assigneeStaffId` into zustand and nowhere else: no server saw it, no
// worker was told, and the roster panel counted those local writes back as
// "N active" — a number the browser invented that did not survive a reload. R13
// was recorded in `COMPLAINT_ENGINE_PRD.md` and in the handoff's ruling table
// and then never executed, which is exactly the kind of thing a test is for:
// this file is what stops it being re-added by somebody reading the old plan.
//
// What replaces it is the link R13 named. Complaints stay department-pooled
// (product ruling 1), so there is no per-person complaint ownership to offer
// here at all — the assignment that exists is a work order, and it has a screen.

const mocks = vi.hoisted(() => ({ api: vi.fn(), state: {} }));

vi.mock('../../lib/api/client', () => ({ api: mocks.api }));
vi.mock('../../store/useApp', () => ({
  useApp: (selector) => (selector ? selector(mocks.state) : mocks.state),
}));

const complaint = {
  id: 'complaint-1',
  title: 'Leaking tap',
  description: 'Dripping since Tuesday',
  category: 'Plumbing',
  status: 'Pending',
  urgency: 'Medium',
  flat: 'B-402',
  raisedBy: 'Meera',
  assignee: 'Unassigned',
  date: '2026-08-20',
  updatedAt: '2026-08-20T09:00:00.000Z',
  comments: [],
};

const department = {
  id: 'dept-1',
  name: 'Maintenance',
  description: 'Fixes things',
  categories: ['Plumbing'],
  categoryIds: ['cat-1'],
  skills: [],
  skillIds: [],
  operatingHours: { start: '09:00', end: '18:00' },
  status: 'Active',
  staff: [
    { id: 'staff-1', name: 'Ravi Kumar', role: 'Plumber', rank: 'member', status: 'active' },
  ],
};

beforeEach(() => {
  mocks.state = {
    complaints: [complaint],
    updateComplaint: vi.fn(),
    addComplaintComment: vi.fn(),
  };
  mocks.api.mockReset().mockImplementation((path) => {
    if (path.startsWith('/departments?')) {
      return Promise.resolve({ items: [department], total: 1 });
    }
    return Promise.resolve([]);
  });
});

function renderScreen() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/admin/departments/dept-1']}>
        <Routes>
          <Route path="/admin/departments/:departmentId" element={<DepartmentDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('a department’s complaint rows', () => {
  it('offers no assign-to-staff control', async () => {
    renderScreen();
    await screen.findByText('Leaking tap');

    expect(screen.queryByText('Assign to staff')).toBeNull();
    // The select is gone, not merely relabelled: Status is the only one left.
    expect(screen.getAllByRole('combobox')).toHaveLength(1);
  });

  it('offers the work-order screen instead, deep-linked to the complaint', async () => {
    renderScreen();
    await screen.findByText('Leaking tap');

    const link = screen.getByRole('link', { name: /Raise work order/ });
    expect(link.getAttribute('href')).toBe(
      '/admin/departments/dept-1/work-orders?complaint=complaint-1'
    );
  });

  it('no longer counts local assignments back at the roster', async () => {
    renderScreen();
    await screen.findByText('Ravi Kumar');

    expect(screen.queryByText(/\d+ active/)).toBeNull();
  });
});
