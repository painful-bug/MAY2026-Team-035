import { normalizePhoneNumber } from '../utils/phone.js';

export const isSecurityDepartment = (department) =>
  department.name.toLowerCase().includes('security') ||
  department.categories?.some(
    (category) => category.toLowerCase() === 'security'
  );

const isManagerRole = (role = '') => role.toLowerCase() === 'manager';

export const findSecurityCommunityAccount = (departments, phone) => {
  const cleanPhone = normalizePhoneNumber(phone);

  for (const department of departments) {
    if (!isSecurityDepartment(department)) continue;

    const member = department.staff?.find(
      (item) => normalizePhoneNumber(item.phone) === cleanPhone
    );

    if (member) {
      const isManager =
        isManagerRole(member.role) ||
        normalizePhoneNumber(department.phone) === cleanPhone;
      return {
        id: `security-${member.id}`,
        staffId: member.id,
        name: member.name,
        phone: member.phone,
        role: isManager ? 'SecurityManager' : 'Security',
        staffRole: member.role,
        departmentId: department.id,
        departmentName: department.name,
        status:
          department.status === 'Inactive' || member.status === 'Inactive'
            ? 'Inactive'
            : 'Active',
        tower: 'Community',
        flat: isManager ? 'Operations Centre' : 'Main Gate',
      };
    }

    if (
      department.head &&
      normalizePhoneNumber(department.phone) === cleanPhone
    ) {
      return {
        id: `security-manager-${department.id}`,
        staffId: null,
        name: department.head,
        phone: department.phone,
        role: 'SecurityManager',
        staffRole: 'Manager',
        departmentId: department.id,
        departmentName: department.name,
        status: department.status === 'Inactive' ? 'Inactive' : 'Active',
        tower: 'Community',
        flat: 'Operations Centre',
      };
    }
  }

  return null;
};
