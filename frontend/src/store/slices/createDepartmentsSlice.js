import { genId } from '../../lib/ids';
import { api } from '../../lib/api/client';

export const createDepartmentsSlice = (set, get) => ({
  departments: [],

  createDepartment: async (departmentData) => {
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
    const payload = {
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
        name: member.name?.trim() || '',
        phone: member.phone?.trim() || '',
      })),
    };

    try {
      const response = await api('/departments', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      // Use the response data if possible, else optimistic
      const newDept = {
        ...payload,
        id: response.id || genId('dept'),
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
    } catch (e) {
      get().showToast(e.message || 'Failed to create department', 'error');
      return null;
    }
  },

  updateDepartment: async (departmentId, departmentData) => {
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
              id: member.id || undefined, // Backend may generate id
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

    try {
      await api(`/departments/${departmentId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: updated.name,
          description: updated.description,
          categories: updated.categories,
          head: updated.head,
          email: updated.email,
          phone: updated.phone,
          operatingHours: updated.operatingHours,
          slaHours: updated.slaHours,
          status: updated.status,
          staff: departmentData.staff !== undefined ? updated.staff : undefined
        })
      });
      get().showToast(`${updated.name} updated successfully.`, 'success');
      get().addActivity(`Department "${updated.name}" was updated`, 'department');
    } catch (e) {
      get().showToast(e.message || 'Failed to update department', 'error');
    }
    return updated;
  },

  setDepartmentStatus: async (departmentId, status) => {
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

    try {
      await api(`/departments/${departmentId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status })
      });
      get().showToast(`${department.name} is now ${status.toLowerCase()}.`, 'success');
      get().addActivity(
        `Department "${department.name}" marked ${status.toLowerCase()}`,
        'department'
      );
    } catch (e) {
      get().showToast(e.message || 'Failed to update status', 'error');
    }
    return { ...department, status };
  },

  deleteDepartment: async (departmentId) => {
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

    try {
      await api(`/departments/${departmentId}`, { method: 'DELETE' });
      set((state) => ({
        departments: state.departments.filter(
          (item) => item.id !== departmentId
        ),
      }));
      get().showToast(`${department.name} deleted.`, 'success');
      get().addActivity(`Department "${department.name}" was deleted`, 'department');
      return { ok: true };
    } catch (e) {
      get().showToast(e.message || 'Failed to delete department', 'error');
      return { ok: false, reason: 'api-error' };
    }
  },
});
