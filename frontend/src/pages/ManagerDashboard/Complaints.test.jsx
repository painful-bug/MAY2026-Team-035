import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ManagerComplaints from './Complaints';

// The cover banner (product ruling 3, 2026-08-21).
//
// When a department's last supervisor is removed, `20260821200000` §4 re-stamps
// their live work orders onto whoever inherits them and sends the manager one
// `department.supervision_uncovered` notification. A notification is a moment,
// and the moment passes; the queue stays the manager's until somebody invites a
// new supervisor. This banner is the standing half of that, and the property
// worth pinning is that it is *conditional* — a permanent banner is furniture
// and stops being read.
//
// No new workspace sits behind it and none is needed: `can_manage_department`
// implies `can_supervise_department` (`0036` §435), so this screen is already a
// strict superset of the supervisor's.

const mocks = vi.hoisted(() => ({ department: vi.fn() }));

vi.mock('./useManagerDepartment', () => ({
  useManagerDepartment: () => mocks.department(),
}));

// The two panels below the banner each make their own reads; neither is what
// this file is about, so both are stubbed to nothing.
vi.mock('../../features/complaints/components/ChangeRequests', () => ({
  default: () => <div data-testid="change-requests" />,
}));
vi.mock('../../features/complaints/components/DepartmentComplaintList', () => ({
  default: () => <div data-testid="complaint-list" />,
}));

// Read off `role="status"` rather than by text: the sentence is split across
// JSX text nodes by its two `&apos;` entities, and a matcher that happened to
// work only because of where the wrapping fell would break on a re-indent.
const banner = () =>
  screen.queryAllByRole('status').find((node) =>
    /covering this department.s complaint queue/.test(
      node.textContent.replace(/\s+/g, ' ')
    )
  ) || null;

const scope = (roster) => ({
  departmentId: 'dept-1',
  department: { id: 'dept-1', name: 'Maintenance' },
  roster,
  pendingInvitations: [],
  isLoading: false,
  error: null,
});

const member = (rank) => ({ id: `staff-${rank}`, name: 'Someone', rank, status: 'active' });

beforeEach(() => {
  mocks.department.mockReset();
});

function renderScreen() {
  return render(
    <MemoryRouter initialEntries={['/manager/complaints']}>
      <ManagerComplaints />
    </MemoryRouter>
  );
}

describe('the manager’s complaints screen', () => {
  it('says nothing while the department still has a supervisor', () => {
    mocks.department.mockReturnValue(scope([member('supervisor'), member('member')]));
    renderScreen();
    expect(banner()).toBeNull();
  });

  it('says who is covering once the last supervisor has gone', () => {
    mocks.department.mockReturnValue(scope([member('manager'), member('member')]));
    renderScreen();
    expect(banner()).toBeTruthy();
  });

  it('says it for an empty roster too — nobody is not somebody', () => {
    mocks.department.mockReturnValue(scope([]));
    renderScreen();
    expect(banner()).toBeTruthy();
  });

  it('says nothing before the department read has answered', () => {
    // `department: null` is "not known yet", not "has no supervisors". A banner
    // shown during the first paint and withdrawn a moment later is a flicker
    // that reads as a bug.
    mocks.department.mockReturnValue({ ...scope([]), department: null });
    renderScreen();
    expect(banner()).toBeNull();
  });

  it('still explains itself when the manager has no department at all', () => {
    mocks.department.mockReturnValue({ ...scope([]), departmentId: null });
    renderScreen();
    expect(banner()).toBeNull();
    expect(screen.getByText(/No department is assigned/)).toBeTruthy();
  });
});
