import { genId } from '../../lib/ids';
import { todayISO, shortTime } from '../../lib/dates';
import { initialVisitors } from '../../data/visitors';
import { useAuthStore } from '../authStore';

export const createVisitorsSlice = (set, get) => ({
  visitors: initialVisitors,

  preapproveVisitor: (visitorData) => {
    const currentUser = useAuthStore.getState().currentUser;
    const newVisitor = {
      id: genId('v'),
      name: visitorData.name,
      phone: visitorData.phone,
      purpose: visitorData.purpose,
      flat: currentUser ? `${currentUser.flat}` : 'B-1204',
      tower: currentUser ? `${currentUser.tower}` : 'B',
      date: visitorData.date || todayISO(),
      status: 'Expected',
      eta: visitorData.time || '04:00 PM',
      code: `PG-${Math.floor(1000 + Math.random() * 9000)}`,
    };
    set((s) => ({ visitors: [newVisitor, ...s.visitors] }));
    get().showToast(`Visitor ${visitorData.name} Pre-approved! Code: ${newVisitor.code}`, 'success');
    get().addActivity(`You pre-approved visitor ${visitorData.name}`, 'visitor');
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
