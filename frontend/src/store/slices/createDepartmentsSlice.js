import { genId } from '../../lib/ids';

export const createDepartmentsSlice = (set, get) => ({
  departments: [],

  createDepartment: (departmentData) => {
    const name = departmentData.name.trim();
    const duplicate = get().departments.some(
      (department) => department.name.toLowerCase() === name.toLowerCase()
    );
    if (!name || duplicate) {
      get().showToast(
        duplicate ? 'A department with this name already exists.' : 'Department name is required.',
        'error'
      );
      return null;
    }

    const now = new Date().toISOString();
    const newDept = {
      id: genId('dept'),
      name,
      description: departmentData.description?.trim() || '',
      categories: [...new Set(departmentData.categories ?? [])],
      head: departmentData.head?.trim() || '',
      email: departmentData.email?.trim() || '',
      phone: departmentData.phone?.trim() || '',
      operatingHours: departmentData.operatingHours ?? {
        start: '09:00',
        end: '18:00',
      },
      slaHours: Math.max(1, Number(departmentData.slaHours) || 24),
      status: departmentData.status || 'Active',
      staff: (departmentData.staff ?? []).map((member) => ({
        ...member,
        id: member.id || genId('staff'),
        name: member.name?.trim() || '',
        phone: member.phone?.trim() || '',
      })),
      createdAt: now,
      updatedAt: now,
    };
    set((s) => ({ departments: [newDept, ...s.departments] }));
    get().showToast(`${name} created successfully.`, 'success');
    get().addActivity(
      `Department "${name}" created with ${newDept.staff.length} staff member(s)`,
      'department'
    );
    return newDept;
  },

  updateDepartment: (departmentId, departmentData) => {
    const current = get().departments.find(
      (department) => department.id === departmentId
    );
    if (!current) return null;

    const name = departmentData.name?.trim() || current.name;
    const duplicate = get().departments.some(
      (department) =>
        department.id !== departmentId &&
        department.name.toLowerCase() === name.toLowerCase()
    );
    if (duplicate) {
      get().showToast('A department with this name already exists.', 'error');
      return null;
    }

    const updated = {
      ...current,
      ...departmentData,
      name,
      description:
        departmentData.description === undefined
          ? current.description
          : departmentData.description.trim(),
      head:
        departmentData.head === undefined
          ? current.head
          : departmentData.head.trim(),
      email:
        departmentData.email === undefined
          ? current.email
          : departmentData.email.trim(),
      phone:
        departmentData.phone === undefined
          ? current.phone
          : departmentData.phone.trim(),
      categories:
        departmentData.categories === undefined
          ? current.categories
          : [...new Set(departmentData.categories)],
      staff:
        departmentData.staff === undefined
          ? current.staff
          : departmentData.staff.map((member) => ({
              ...member,
              id: member.id || genId('staff'),
              name: member.name?.trim() || '',
              phone: member.phone?.trim() || '',
            })),
      slaHours: Math.max(
        1,
        Number(departmentData.slaHours ?? current.slaHours) || 24
      ),
      updatedAt: new Date().toISOString(),
    };

    set((state) => ({
      departments: state.departments.map((department) =>
        department.id === departmentId ? updated : department
      ),
    }));
    get().showToast(`${updated.name} updated successfully.`, 'success');
    get().addActivity(`Department "${updated.name}" was updated`, 'department');
    return updated;
  },

  setDepartmentStatus: (departmentId, status) => {
    const department = get().departments.find(
      (item) => item.id === departmentId
    );
    if (!department || !['Active', 'Inactive'].includes(status)) return null;
    set((state) => ({
      departments: state.departments.map((item) =>
        item.id === departmentId
          ? { ...item, status, updatedAt: new Date().toISOString() }
          : item
      ),
    }));
    get().showToast(`${department.name} is now ${status.toLowerCase()}.`, 'success');
    get().addActivity(
      `Department "${department.name}" marked ${status.toLowerCase()}`,
      'department'
    );
    return { ...department, status };
  },

  deleteDepartment: (departmentId) => {
    const department = get().departments.find(
      (item) => item.id === departmentId
    );
    if (!department) return { ok: false, reason: 'not-found' };

    const activeComplaints = get().complaints.filter(
      (complaint) => {
        const category = complaint.category?.toLowerCase() ?? '';
        const ownsCategory =
          Boolean(category) &&
          ((department.categories ?? []).some(
            (item) => item.toLowerCase() === category
          ) ||
            department.name.toLowerCase().includes(category));
        return complaint.status !== 'Resolved' && ownsCategory;
      }
    );
    if (activeComplaints.length > 0) {
      get().showToast(
        `Resolve or reassign ${activeComplaints.length} active complaint${activeComplaints.length === 1 ? '' : 's'} before deleting this department.`,
        'error'
      );
      return {
        ok: false,
        reason: 'active-complaints',
        count: activeComplaints.length,
      };
    }

    set((state) => ({
      departments: state.departments.filter(
        (item) => item.id !== departmentId
      ),
    }));
    get().showToast(`${department.name} deleted.`, 'success');
    get().addActivity(`Department "${department.name}" was deleted`, 'department');
    return { ok: true };
  },
});
