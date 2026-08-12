import { api } from '../../lib/api/client';

// The in-app notification feed. The backend has served this since 0030 and
// re-addressed it to a person in 0041; until Phase 2 Step 5 nothing in the
// frontend called it — only the push service worker honoured `url`.
//
// Same thin shape as workerApi/hiringApi: no state, no caching, no error
// translation. react-query owns the cache.

export const notificationsApi = {
  // { items, unread, page, pageSize, total } — `unread` counts the whole feed,
  // not the page, which is exactly what a badge needs.
  list: ({ unread = false, page = 1, pageSize = 20 } = {}) => {
    const query = new URLSearchParams({ page, pageSize });
    if (unread) query.set('unread', 'true');
    return api(`/notifications?${query}`);
  },
  // Both return { marked, unread } so the badge can be set from the response
  // instead of re-fetching the feed to find out.
  markRead: (notificationId) =>
    api(`/notifications/${notificationId}/read`, { method: 'POST' }),
  markAllRead: () => api('/notifications/read-all', { method: 'POST' }),
};
