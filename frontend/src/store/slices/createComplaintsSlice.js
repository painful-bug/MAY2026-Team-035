import { genId } from '../../lib/ids';
import { todayISO } from '../../lib/dates';
import { initialComplaints } from '../../data/complaints';
import { useAuthStore } from '../authStore';

const getExpectedResolutionAt = (urgency, createdAt) => {
  const hoursByUrgency = { High: 24, Medium: 48, Low: 72 };
  const expectedAt = new Date(createdAt);
  expectedAt.setHours(
    expectedAt.getHours() + (hoursByUrgency[urgency] ?? 48)
  );
  return expectedAt.toISOString();
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
  complaints: initialComplaints,

  raiseComplaint: (complaintData) => {
    const currentUser = useAuthStore.getState().currentUser;
    const createdAt = new Date().toISOString();
    const urgency = complaintData.urgency || 'Low';
    const newComplaint = {
      id: genId('c'),
      title: complaintData.title.trim(),
      description: complaintData.description.trim(),
      raisedBy: currentUser?.name || 'Aakash S.',
      userId: currentUser?.id || 'u1',
      flat: currentUser ? `${currentUser.flat}` : 'B-1204',
      date: todayISO(),
      timeAgo: 'Just Now',
      category: complaintData.category,
      status: 'Pending',
      assignee: 'Unassigned',
      progress: 0,
      urgency,
      location: complaintData.location?.trim() || currentUser?.flat || '',
      attachments: (complaintData.attachments ?? []).map((attachment) => ({
        ...attachment,
      })),
      comments: [],
      createdAt,
      updatedAt: createdAt,
      expectedResolutionAt: getExpectedResolutionAt(urgency, createdAt),
      timeline: [
        createTimelineEvent(
          'raised',
          'Complaint raised',
          'Your complaint was submitted to the management team.',
          currentUser?.name || 'Resident',
          createdAt
        ),
      ],
      hasUnreadUpdate: false,
      resolutionConfirmed: false,
      rating: null,
      residentFeedback: '',
      reopenedCount: 0,
    };
    set((s) => ({ complaints: [newComplaint, ...s.complaints] }));
    get().showToast('Complaint Raised Successfully', 'success');
    get().addActivity(`You raised complaint "${complaintData.title}"`, 'complaint');
    return newComplaint;
  },

  updateComplaint: (complaintId, updatedFields) => {
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
    get().showToast('Updated complaint status', 'success');
    if (updatedFields.status) {
      get().addActivity(`Complaint "${c.title}" status updated to ${updatedFields.status}`, 'complaint');
    }
    return { ...c, ...nextFields, timeline, updatedAt };
  },

  addComplaintComment: (complaintId, message) => {
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
    get().showToast('Comment added', 'success');
    return comment;
  },

  reopenComplaint: (complaintId, reason) => {
    const complaint = get().complaints.find((item) => item.id === complaintId);
    const currentUser = useAuthStore.getState().currentUser;
    const trimmedReason = reason.trim();
    if (!complaint || complaint.status !== 'Resolved' || !trimmedReason) {
      return null;
    }

    const updatedAt = new Date().toISOString();
    const event = createTimelineEvent(
      'reopened',
      'Complaint reopened',
      trimmedReason,
      currentUser?.name ?? 'Resident',
      updatedAt
    );
    set((state) => ({
      complaints: state.complaints.map((item) =>
        item.id === complaintId
          ? {
              ...item,
              status: 'Pending',
              progress: 0,
              assignee: 'Unassigned',
              resolutionConfirmed: false,
              rating: null,
              residentFeedback: '',
              reopenedCount: Number(item.reopenedCount || 0) + 1,
              expectedResolutionAt: getExpectedResolutionAt(
                item.urgency,
                updatedAt
              ),
              timeline: [...getComplaintTimeline(item), event],
              updatedAt,
              hasUnreadUpdate: false,
            }
          : item
      ),
    }));
    get().showToast('Complaint reopened', 'success');
    get().addActivity(`You reopened complaint "${complaint.title}"`, 'complaint');
    return event;
  },

  confirmComplaintResolution: (complaintId, resolutionData) => {
    const complaint = get().complaints.find((item) => item.id === complaintId);
    const currentUser = useAuthStore.getState().currentUser;
    const rating = Number(resolutionData.rating);
    if (
      !complaint ||
      complaint.status !== 'Resolved' ||
      rating < 1 ||
      rating > 5
    ) {
      return null;
    }

    const updatedAt = new Date().toISOString();
    const event = createTimelineEvent(
      'confirmed',
      'Resolution confirmed',
      resolutionData.feedback?.trim()
        ? `Resident feedback: ${resolutionData.feedback.trim()}`
        : `The resident confirmed the resolution with a ${rating}-star rating.`,
      currentUser?.name ?? 'Resident',
      updatedAt
    );
    set((state) => ({
      complaints: state.complaints.map((item) =>
        item.id === complaintId
          ? {
              ...item,
              resolutionConfirmed: true,
              rating,
              residentFeedback: resolutionData.feedback?.trim() ?? '',
              timeline: [...getComplaintTimeline(item), event],
              updatedAt,
              hasUnreadUpdate: false,
            }
          : item
      ),
    }));
    get().showToast('Thank you for your feedback', 'success');
    return event;
  },

  markComplaintRead: (complaintId) =>
    set((state) => ({
      complaints: state.complaints.map((item) =>
        item.id === complaintId ? { ...item, hasUnreadUpdate: false } : item
      ),
    })),
});
