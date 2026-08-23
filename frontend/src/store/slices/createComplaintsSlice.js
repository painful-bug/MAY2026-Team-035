import { genId } from '../../lib/ids';
import { useAuthStore } from '../authStore';
import { api } from '../../lib/api/client';
import { getDashboardSnapshot } from '../../lib/dashboard/dashboardApi';

// What is left here is the **admin** half of the demo store, and only that.
//
// The resident's complaint screen used to raise, reopen, confirm and mark read
// through this slice, and it now calls the API through
// `features/resident/residentApi.js` with react-query holding the result. Those
// four actions are gone rather than kept alongside: two writers for one record
// is how a screen ends up showing a status the server never agreed to.
//
// `raiseComplaint` also computed the SLA deadline in the browser, which the
// database has done since `0031` — a resident could send themselves a
// one-minute deadline and the admin portal could not see it at all. That rule
// left with the function; nothing in the frontend computes it now.
//
// `complaints`, `updateComplaint` and `addComplaintComment` stay because the
// admin and manager screens still read and write them.

// A write the server refused must not stay on screen. Both writers below set
// the store first (the optimistic copy the SSE re-snapshot normally replaces
// within a beat), but a *failed* write fires no SSE event — nothing would ever
// correct the lie. So the catch re-reads the snapshot for server truth, and if
// even that read fails (the network is down, which is usually why the write
// failed), it restores the one row to the last state the server agreed to.
const restoreAfterFailedWrite = async (set, get, priorComplaint) => {
  try {
    get().hydrateDashboard(await getDashboardSnapshot());
  } catch {
    set((s) => ({
      complaints: s.complaints.map((x) =>
        x.id === priorComplaint.id ? priorComplaint : x
      ),
    }));
  }
};

const createTimelineEvent = (type, label, message, actor, createdAt) => ({
  id: genId('event'),
  type,
  label,
  message,
  actor,
  createdAt,
});

const getComplaintTimeline = (complaint) => {
  if (complaint.timeline?.length) {
    return [...complaint.timeline];
  }

  return [
    createTimelineEvent(
      'raised',
      'Complaint raised',
      'The complaint was submitted to the management team.',
      complaint.raisedBy || 'Resident',
      complaint.createdAt ?? `${complaint.date}T09:00:00.000Z`
    ),
  ];
};

export const createComplaintsSlice = (set, get) => ({
  complaints: [],

  updateComplaint: async (complaintId, updatedFields) => {
    const c = get().complaints.find((comp) => comp.id === complaintId);
    if (!c) return null;

    const currentUser = useAuthStore.getState().currentUser;
    const updatedAt = new Date().toISOString();
    const timeline = getComplaintTimeline(c);

    if (updatedFields.assignee && updatedFields.assignee !== c.assignee) {
      timeline.push(
        createTimelineEvent(
          'assigned',
          'Technician assigned',
          `${updatedFields.assignee} was assigned to this complaint.`,
          currentUser?.name || 'Management',
          updatedAt
        )
      );
    }

    if (updatedFields.status && updatedFields.status !== c.status) {
      const labels = {
        Pending: 'Moved to pending',
        'In Progress': 'Work started',
        Resolved: 'Marked resolved',
      };
      timeline.push(
        createTimelineEvent(
          updatedFields.status.toLowerCase().replaceAll(' ', '-'),
          labels[updatedFields.status] ?? `Status: ${updatedFields.status}`,
          updatedFields.updateNote?.trim() ||
            `The complaint status changed to ${updatedFields.status}.`,
          currentUser?.name || 'Management',
          updatedAt
        )
      );
    } else if (updatedFields.updateNote?.trim()) {
      timeline.push(
        createTimelineEvent(
          'update',
          'Management update',
          updatedFields.updateNote.trim(),
          currentUser?.name || 'Management',
          updatedAt
        )
      );
    }

    const nextFields = { ...updatedFields };
    delete nextFields.updateNote;
    set((s) => ({
      complaints: s.complaints.map((x) =>
        x.id === complaintId
          ? {
              ...x,
              ...nextFields,
              timeline,
              updatedAt,
              hasUnreadUpdate: true,
            }
          : x
      ),
    }));

    try {
      await api(`/complaints/${complaintId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: updatedFields.status,
          progress: updatedFields.progress,
          assignee: updatedFields.assignee,
          expectedResolutionAt: updatedFields.expectedResolutionAt,
          updateNote: updatedFields.updateNote,
        })
      });
      get().showToast('Updated complaint status', 'success');
      if (updatedFields.status) {
        get().addActivity(`Complaint "${c.title}" status updated to ${updatedFields.status}`, 'complaint');
      }
    } catch (e) {
      get().showToast(e.message || 'Failed to update complaint on server', 'error');
      await restoreAfterFailedWrite(set, get, c);
      return null;
    }

    return { ...c, ...nextFields, timeline, updatedAt };
  },

  addComplaintComment: async (complaintId, message) => {
    const complaint = get().complaints.find((item) => item.id === complaintId);
    const currentUser = useAuthStore.getState().currentUser;
    const trimmedMessage = message.trim();
    if (!complaint || !trimmedMessage) return null;

    const createdAt = new Date().toISOString();
    const comment = {
      id: genId('comment'),
      message: trimmedMessage,
      authorId: currentUser?.id ?? 'resident',
      authorName: currentUser?.name ?? 'Resident',
      authorRole: currentUser?.role ?? 'Resident',
      createdAt,
    };
    set((state) => ({
      complaints: state.complaints.map((item) =>
        item.id === complaintId
          ? {
              ...item,
              comments: [...(item.comments ?? []), comment],
              updatedAt: createdAt,
              hasUnreadUpdate: currentUser?.role === 'Admin',
            }
          : item
      ),
    }));

    try {
      await api(`/complaints/${complaintId}/comments`, {
        method: 'POST',
        body: JSON.stringify({ message: trimmedMessage, visibility: 'resident' })
      });
      get().showToast('Comment added', 'success');
    } catch (e) {
      get().showToast(e.message || 'Failed to add comment on server', 'error');
      await restoreAfterFailedWrite(set, get, complaint);
      return null;
    }

    return comment;
  },
});
