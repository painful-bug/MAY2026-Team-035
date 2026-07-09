import { genId } from '../../lib/ids';
import { initialDepartments } from '../../data/departments';

export const createDepartmentsSlice = (set, get) => ({
  departments: initialDepartments,

  createDepartment: ({ name, categories, staff }) => {
    const newDept = {
      id: genId('dept'),
      name,
      categories,
      staff: staff.map((member) => ({ ...member, id: genId('staff') })),
    };
    set((s) => ({ departments: [newDept, ...s.departments] }));
    get().showToast(`${name} created successfully.`, 'success');
    get().addActivity(`Department "${name}" created with ${staff.length} staff member(s)`, 'department');
    return newDept;
  },
});
