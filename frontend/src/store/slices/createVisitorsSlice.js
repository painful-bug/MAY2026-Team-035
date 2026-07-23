import { genId } from '../../lib/ids';
import { todayISO, shortTime } from '../../lib/dates';
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
    const qrToken = genId('visitor-pass');
    const qrPayload = JSON.stringify({
      type: 'homebandhu-visitor-pass',
      version: 1,
      passId: id,
      token: qrToken,
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
      code: `PG-${Math.floor(1000 + Math.random() * 9000)}`,
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
    set((s) => ({
      visitors: s.visitors.map((x) =>
        x.id === visitorId ? { ...x, status: 'Checked In', checkInTime: shortTime() } : x
      ),
    }));
    get().showToast(`Approved entry for ${v ? v.name : 'visitor'}`, 'success');
    if (v) get().addActivity(`Approved entry for visitor ${v.name}`, 'visitor');
  },
});
