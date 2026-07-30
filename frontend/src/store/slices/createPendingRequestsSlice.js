import { genId } from '../../lib/ids';
import { todayISO } from '../../lib/dates';

// Self-signup requests awaiting admin approval. Approving one promotes it to a
// resident user + seeds a default unpaid maintenance invoice (touches the users
// and payments slices via a single combined set — they all share this store).
export const createPendingRequestsSlice = (set, get) => ({
  pendingRequests: [],

  addPendingRequest: (formData) => {
    const newRequest = {
      id: genId('pr'),
      name: formData.fullName,
      email: formData.email,
      phone: formData.mobile,
      tower: formData.tower || 'A',
      flat: formData.flatNumber,
      date: todayISO(),
    };
    set((s) => ({ pendingRequests: [...s.pendingRequests, newRequest] }));
    get().showToast('Registration Request Submitted Successfully. Awaiting admin approval.', 'success');
  },

  acceptRequest: (requestId) => {
    const request = get().pendingRequests.find((r) => r.id === requestId);
    if (!request) return;

    const newResident = {
      id: genId('u'),
      name: request.name,
      email: request.email,
      role: 'Resident',
      phone: request.phone,
      tower: request.tower,
      flat: request.flat,
      apartmentId: `${request.tower}-${request.flat}`,
      status: 'Active',
    };

    const newPayment = {
      id: genId('pay'),
      title: 'Maintenance Fee - July 2026',
      amount: 4250,
      dueDate: '2026-07-15',
      status: 'Unpaid',
      billPeriod: 'July 1, 2026 - July 31, 2026',
      userId: newResident.id,
      flat: newResident.flat,
      tower: newResident.tower,
    };

    set((s) => ({
      users: [...s.users, newResident],
      pendingRequests: s.pendingRequests.filter((r) => r.id !== requestId),
      payments: [...s.payments, newPayment],
    }));

    get().showToast(`Approved registration for ${request.name}`, 'success');
    get().addActivity(`Admin approved registration for ${request.name} (${request.flat})`, 'general');
  },

  rejectRequest: (requestId) => {
    const request = get().pendingRequests.find((r) => r.id === requestId);
    set((s) => ({ pendingRequests: s.pendingRequests.filter((r) => r.id !== requestId) }));
    if (request) get().showToast(`Rejected registration for ${request.name}`, 'info');
  },
});
