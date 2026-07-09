import { genId } from '../../lib/ids';
import { todayISO } from '../../lib/dates';
import { initialComplaints } from '../../data/complaints';
import { useAuthStore } from '../authStore';

export const createComplaintsSlice = (set, get) => ({
  complaints: initialComplaints,

  raiseComplaint: (complaintData) => {
    const currentUser = useAuthStore.getState().currentUser;
    const newComplaint = {
      id: genId('c'),
      title: complaintData.title,
      description: complaintData.description,
      raisedBy: currentUser?.name || 'Aakash S.',
      userId: currentUser?.id || 'u1',
      flat: currentUser ? `${currentUser.flat}` : 'B-1204',
      date: todayISO(),
      timeAgo: 'Just Now',
      category: complaintData.category,
      status: 'Pending',
      assignee: 'Unassigned',
      progress: 0,
      urgency: complaintData.urgency || 'Low',
    };
    set((s) => ({ complaints: [newComplaint, ...s.complaints] }));
    get().showToast('Complaint Raised Successfully', 'success');
    get().addActivity(`You raised complaint "${complaintData.title}"`, 'complaint');
  },

  updateComplaint: (complaintId, updatedFields) => {
    const c = get().complaints.find((comp) => comp.id === complaintId);
    set((s) => ({
      complaints: s.complaints.map((x) => (x.id === complaintId ? { ...x, ...updatedFields } : x)),
    }));
    get().showToast('Updated complaint status', 'success');
    if (c && updatedFields.status) {
      get().addActivity(`Complaint "${c.title}" status updated to ${updatedFields.status}`, 'complaint');
    }
  },
});
