import { genId } from '../../lib/ids';
import { initialUsers } from '../../data/users';

// The people directory: residents + admins. Also owns admin resident-management
// (add via invite, edit, remove) and the resident self-service "add another
// number to my flat". Invite minting itself lives in the invitations slice;
// addResident just calls get().issueInvite after creating the records.
export const createUsersSlice = (set, get) => ({
  users: initialUsers,

  addAdmin: (adminData) => {
    const newAdmin = {
      id: genId('u'),
      name: adminData.name,
      email: adminData.email,
      role: 'Admin',
      phone: adminData.phone || '+91 99999 99999',
      tower: adminData.tower || 'A',
      flat: adminData.flat || 'Admin Office',
      apartmentId: adminData.flat || 'Admin Office',
      status: 'Active',
    };
    set((s) => ({ users: [...s.users, newAdmin] }));
    get().showToast(`Added ${adminData.name} as an Admin`, 'success');
    get().addActivity(`Admin added new admin: ${adminData.name}`, 'general');
  },

  // Admin "Add Resident": create a record per phone (status 'Invited') for the
  // flat and mint one single-use invite covering all of them. Returns the invite
  // so the caller can show the link/code.
  addResident: (residentData) => {
    const apartmentId = `${residentData.tower}-${residentData.flatNumber}`;
    const phones = (residentData.phones || []).map((p) => p.trim()).filter(Boolean);

    const newUsers = phones.map((phone, i) => ({
      id: genId('u'),
      name: i === 0 ? residentData.name : `${residentData.name} · Member ${i + 1}`,
      email: i === 0 ? residentData.email : '',
      role: 'Resident',
      phone,
      tower: residentData.tower,
      flat: apartmentId,
      apartmentId,
      status: 'Invited',
    }));

    set((s) => ({ users: [...s.users, ...newUsers] }));
    const invite = get().issueInvite({ apartmentId, phones });
    get().showToast(`Invite created for ${residentData.name} (${apartmentId})`, 'success');
    get().addActivity(`Admin invited resident ${residentData.name} to ${apartmentId}`, 'general');
    return invite;
  },

  editResident: (userId, updated) => {
    set((s) => ({ users: s.users.map((u) => (u.id === userId ? { ...u, ...updated } : u)) }));
    get().showToast('Resident details updated', 'success');
    get().addActivity(`Admin updated resident ${updated.name || ''}`.trim(), 'general');
  },

  removeResident: (userId) => {
    const u = get().users.find((x) => x.id === userId);
    set((s) => ({ users: s.users.filter((x) => x.id !== userId) }));
    if (u) {
      get().showToast(`Removed resident ${u.name}`, 'info');
      get().addActivity(`Admin removed resident ${u.name} (${u.flat})`, 'general');
    }
  },

  // Resident self-service (PRD #8): add another number to my own flat, no admin.
  addPhoneToApartment: (apartmentId, phone, name) => {
    const flatUser = get().users.find((u) => u.apartmentId === apartmentId);
    const newUser = {
      id: genId('u'),
      name: name || 'New Member',
      email: '',
      role: 'Resident',
      phone: phone.trim(),
      tower: flatUser?.tower || '',
      flat: flatUser?.flat || apartmentId,
      apartmentId,
      status: 'Active',
    };
    set((s) => ({ users: [...s.users, newUser] }));
    get().showToast(`Added ${phone} to your flat`, 'success');
    get().addActivity(`New number added to ${newUser.flat}`, 'general');
    return newUser;
  },
});
