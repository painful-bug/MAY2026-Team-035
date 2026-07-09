import { genId } from '../../lib/ids';
import { longDate } from '../../lib/dates';
import { initialNotices } from '../../data/notices';

export const createNoticesSlice = (set, get) => ({
  notices: initialNotices,

  addNotice: (noticeData) => {
    const newNotice = {
      id: genId('n'),
      title: noticeData.title,
      description: noticeData.description,
      date: longDate(),
      timeAgo: 'Today',
      urgency: noticeData.urgency || 'Info',
      category: noticeData.category || 'General',
    };
    set((s) => ({ notices: [newNotice, ...s.notices] }));
    get().showToast(`Notice "${noticeData.title}" posted successfully`, 'success');
    get().addActivity(`Admin posted new notice: "${noticeData.title}"`, 'notice');
  },
});
