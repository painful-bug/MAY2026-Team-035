import { genId } from '../../lib/ids';
import { todayISO, shortTime } from '../../lib/dates';
import {
  generateVisitorSecurityCode,
  getVisitorSecurityCode,
} from '../../lib/visitorPasses';
import { initialVisitors } from '../../data/visitors';
import { useAuthStore } from '../authStore';

export const createVisitorsSlice = (set, get) => ({
  visitors: initialVisitors,

  preapproveVisitor: (visitorData) => {
    const currentUser = useAuthStore.getState().currentUser;
    const id = genId('v');
    const guestCount = Math.max(1, Number(visitorData.guestCount) || 1);
    const purposeDetails = visitorData.purposeDetails?.trim() || '';
    const purposeLabel =
      visitorData.purpose === 'Other'
        ? purposeDetails || 'Other'
        : visitorData.purpose;
    const securityCode = generateVisitorSecurityCode(get().visitors);
    const qrToken = genId('visitor-pass');
    const qrPayload = JSON.stringify({
      type: 'homebandhu-visitor-pass',
      version: 2,
      passId: id,
      token: qrToken,
      securityCode,
      guestCount,
    });
    const newVisitor = {
      id,
      name: `${purposeLabel} group`,
      phone: '',
      purpose: visitorData.purpose,
      purposeDetails,
      flat: currentUser ? `${currentUser.flat}` : 'B-1204',
      tower: currentUser ? `${currentUser.tower}` : 'B',
      date: visitorData.date || todayISO(),
      status: 'Expected',
      eta: visitorData.time || '16:00',
      expectedDate: visitorData.date || todayISO(),
      expectedTime: visitorData.time || '16:00',
      guestCount,
      securityCode,
      // Keep the legacy field populated while persisted visitor data migrates.
      code: securityCode,
      qrToken,
      qrPayload,
      passType: 'Group QR',
      createdAt: new Date().toISOString(),
    };
    set((s) => ({ visitors: [newVisitor, ...s.visitors] }));
    get().showToast(
      `QR pass generated for ${guestCount} guest${guestCount === 1 ? '' : 's'}`,
      'success'
    );
    get().addActivity(
      `You generated a QR for a ${guestCount}-person ${purposeLabel.toLowerCase()} group`,
      'visitor'
    );
    return newVisitor;
  },

  approveVisitorRequest: (visitorId) => {
    const v = get().visitors.find((vis) => vis.id === visitorId);
    if (!v || v.status !== 'Pending Approval') return null;
    set((s) => ({
      visitors: s.visitors.map((x) =>
        x.id === visitorId
          ? {
              ...x,
              status: 'Approved',
              approvedAt: new Date().toISOString(),
              approvedBy: useAuthStore.getState().currentUser?.name || 'Resident',
            }
          : x
      ),
    }));
    get().showToast(`Approved entry request for ${v.name}`, 'success');
    get().addActivity(`Approved entry request for visitor ${v.name}`, 'visitor');
    return { ...v, status: 'Approved' };
  },

  rejectVisitorRequest: (visitorId) => {
    const visitor = get().visitors.find((item) => item.id === visitorId);
    if (!visitor || visitor.status !== 'Pending Approval') return null;

    set((state) => ({
      visitors: state.visitors.map((item) =>
        item.id === visitorId
          ? {
              ...item,
              status: 'Rejected',
              rejectedAt: new Date().toISOString(),
              rejectedBy:
                useAuthStore.getState().currentUser?.name || 'Resident',
            }
          : item
      ),
    }));
    get().showToast(`Entry request for ${visitor.name} was rejected.`, 'info');
    get().addActivity(`Rejected visitor request for ${visitor.name}`, 'visitor');
    return { ...visitor, status: 'Rejected' };
  },

  requestVisitorApproval: (visitorData) => {
    const currentUser = useAuthStore.getState().currentUser;
    if (currentUser?.role !== 'Security') return null;

    const id = genId('v');
    const guestCount = Math.max(1, Number(visitorData.guestCount) || 1);
    const securityCode = generateVisitorSecurityCode(get().visitors);
    const qrToken = genId('visitor-pass');
    const qrPayload = JSON.stringify({
      type: 'homebandhu-visitor-pass',
      version: 2,
      passId: id,
      token: qrToken,
      securityCode,
      guestCount,
    });
    const purpose = visitorData.purpose || 'Guest';
    const visitor = {
      id,
      name: visitorData.visitorLabel?.trim() || `${purpose} visitor`,
      phone: '',
      purpose,
      purposeDetails: visitorData.purposeDetails?.trim() || '',
      flat: visitorData.flat,
      tower: visitorData.tower,
      date: visitorData.date || todayISO(),
      status: 'Pending Approval',
      eta: visitorData.time || shortTime(),
      expectedDate: visitorData.date || todayISO(),
      expectedTime: visitorData.time || shortTime(),
      guestCount,
      securityCode,
      code: securityCode,
      qrToken,
      qrPayload,
      passType: 'Gate approval request',
      requestedById: currentUser.id,
      requestedBy: currentUser.name,
      requestedAt: new Date().toISOString(),
      createdAt: new Date().toISOString(),
    };

    set((state) => ({ visitors: [visitor, ...state.visitors] }));
    get().showToast(`Approval request sent to Flat ${visitor.flat}.`, 'success');
    get().addActivity(
      `${currentUser.name} requested visitor approval from Flat ${visitor.flat}`,
      'visitor'
    );
    return visitor;
  },

  checkInVisitor: (visitorId) => {
    const currentUser = useAuthStore.getState().currentUser;
    const visitor = get().visitors.find((item) => item.id === visitorId);
    if (!visitor) return { ok: false, message: 'Visitor pass was not found.' };
    if (visitor.status === 'Pending Approval') {
      return { ok: false, message: 'Resident approval is still pending.' };
    }
    if (!['Expected', 'Approved'].includes(visitor.status)) {
      return {
        ok: false,
        message:
          visitor.status === 'Checked In'
            ? 'This visitor is already checked in.'
            : `This pass cannot be used because it is ${visitor.status.toLowerCase()}.`,
      };
    }

    const checkInTime = shortTime();
    set((state) => ({
      visitors: state.visitors.map((item) =>
        item.id === visitorId
          ? {
              ...item,
              status: 'Checked In',
              checkInTime,
              checkedInAt: new Date().toISOString(),
              checkedInBy: currentUser?.name || 'Security',
            }
          : item
      ),
    }));
    get().showToast(`${visitor.name} checked in successfully.`, 'success');
    get().addActivity(
      `${visitor.name} checked in at ${checkInTime} by ${currentUser?.name || 'security'}`,
      'visitor'
    );
    return {
      ok: true,
      visitor: { ...visitor, status: 'Checked In', checkInTime },
    };
  },

  verifyVisitorPass: (credential) => {
    const rawCredential = String(credential || '').trim();
    if (!rawCredential) {
      return { ok: false, message: 'Enter or scan a visitor security code.' };
    }

    let payload = null;
    try {
      payload = JSON.parse(rawCredential);
    } catch {
      payload = null;
    }

    const normalizedCode = rawCredential.toUpperCase();
    const visitor = get().visitors.find((item) => {
      if (payload?.passId && payload?.token) {
        return item.id === payload.passId && item.qrToken === payload.token;
      }
      if (payload?.securityCode) {
        return (
          getVisitorSecurityCode(item).toUpperCase() ===
          String(payload.securityCode).toUpperCase()
        );
      }
      return getVisitorSecurityCode(item).toUpperCase() === normalizedCode;
    });

    if (!visitor) {
      return {
        ok: false,
        message: 'No valid visitor pass matches this QR or security code.',
      };
    }
    return get().checkInVisitor(visitor.id);
  },

  checkOutVisitor: (visitorId) => {
    const currentUser = useAuthStore.getState().currentUser;
    const visitor = get().visitors.find((item) => item.id === visitorId);
    if (!visitor || visitor.status !== 'Checked In') {
      return { ok: false, message: 'Only checked-in visitors can check out.' };
    }

    const checkOutTime = shortTime();
    set((state) => ({
      visitors: state.visitors.map((item) =>
        item.id === visitorId
          ? {
              ...item,
              status: 'Checked Out',
              checkOutTime,
              checkedOutAt: new Date().toISOString(),
              checkedOutBy: currentUser?.name || 'Security',
            }
          : item
      ),
    }));
    get().showToast(`${visitor.name} checked out.`, 'success');
    get().addActivity(
      `${visitor.name} checked out at ${checkOutTime}`,
      'visitor'
    );
    return { ok: true };
  },
});
