import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createDepartmentsSlice } from './createDepartmentsSlice';
import { api } from '../../lib/api/client';

// Owner-approved product ruling (2026-08-30): an admin-created department that
// Departments.jsx's `isSecurityDepartment` heuristic flags must actually carry
// `kind: 'security'` on the wire, not an implicit NULL — `department_schemas.py`
// accepts it on both create and update, and `professional_membership_role(null)`
// otherwise resolves every member of it to 'worker'. Departments.jsx computes
// the heuristic and passes `kind` through on the `departmentData` it hands to
// the slice; these tests pin what the slice does with that field, not the
// heuristic itself (that lives in Departments.jsx).

vi.mock('../../lib/api/client', () => ({ api: vi.fn() }));

// Same (set, get) contract as createComplaintsSlice.test.js — real slice
// functions, no full appStore.
const buildStore = () => {
  let state;
  const set = (updater) => {
    state = {
      ...state,
      ...(typeof updater === 'function' ? updater(state) : updater),
    };
  };
  const get = () => state;
  state = {
    ...createDepartmentsSlice(set, get),
    departments: [],
    complaints: [],
    showToast: vi.fn(),
    addActivity: vi.fn(),
  };
  return get;
};

const baseDepartmentData = () => ({
  name: 'Plumbing',
  description: '',
  categories: [],
  head: '',
  email: '',
  phone: '',
  operatingHours: { start: '09:00', end: '18:00' },
  slaHours: 24,
  status: 'Active',
  staff: [],
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('createDepartment kind', () => {
  it('sends kind: "security" when the caller computed it', async () => {
    const get = buildStore();
    api.mockResolvedValueOnce({ id: 'dept-1' });

    await get().createDepartment({ ...baseDepartmentData(), name: 'Security', kind: 'security' });

    expect(api).toHaveBeenCalledWith('/departments', expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('"kind":"security"'),
    }));
    expect(get().departments[0].kind).toBe('security');
  });

  it('sends no kind key for a non-security department', async () => {
    const get = buildStore();
    api.mockResolvedValueOnce({ id: 'dept-2' });

    await get().createDepartment({ ...baseDepartmentData(), kind: null });

    const [, options] = api.mock.calls[0];
    expect(JSON.parse(options.body)).not.toHaveProperty('kind');
  });
});

describe('updateDepartment kind', () => {
  const existing = () => ({
    id: 'dept-1',
    name: 'Plumbing',
    description: '',
    categories: [],
    head: '',
    email: '',
    phone: '',
    operatingHours: { start: '09:00', end: '18:00' },
    slaHours: 24,
    status: 'Active',
    staff: [],
  });

  it('sends kind: "security" on an edit that now matches the heuristic', async () => {
    const get = buildStore();
    get().departments.push(existing());
    api.mockResolvedValueOnce({});

    await get().updateDepartment('dept-1', {
      ...baseDepartmentData(),
      name: 'Security',
      kind: 'security',
    });

    const [, options] = api.mock.calls[0];
    expect(JSON.parse(options.body).kind).toBe('security');
  });

  it('omits kind on an edit that did not match the heuristic, leaving the stored value alone', async () => {
    const get = buildStore();
    get().departments.push(existing());
    api.mockResolvedValueOnce({});

    await get().updateDepartment('dept-1', { ...baseDepartmentData(), kind: null });

    const [, options] = api.mock.calls[0];
    expect(JSON.parse(options.body)).not.toHaveProperty('kind');
  });
});
