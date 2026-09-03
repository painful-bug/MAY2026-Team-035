import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCheck, Inbox } from 'lucide-react';
import { notificationsApi } from '../../features/notifications/notificationsApi';
import { portalNotificationUrl } from '../../features/notifications/portalUrl';
import { NOTIFICATION_EVENT_MAP } from '../../lib/realtime/portalMaps';
import { useLiveUpdates, useSseFallbackInterval } from '../../lib/realtime/useLiveUpdates';
import { useApp } from '../../store/useApp';

// The real bell. Until Phase 2 Step 5 the only bell in the app was a hard-coded
// red dot over demo data; this one reads GET /notifications and, on click,
// marks the row read and navigates wherever its `url` points — which is how a
// "termination application" notification lands on the employee page.
//
// Mounted in Header.jsx (admin + resident) and WorkerLayout (which has no
// header, so it grew a slim top strip for exactly this).

function when(iso) {
  const then = new Date(iso);
  const minutes = Math.round((Date.now() - then.getTime()) / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return then.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const currentUser = useApp((state) => state.currentUser);

  // The bell carries its own live-update subscription rather than relying on a
  // layout's, because it mounts in four portals and one of them — admin — has
  // no layout-level mount at all. It is a subscription to the tab's single
  // shared `EventSource`, not a connection of its own.
  //
  // `notification.created` is audience `member`: the frame arrives for the one
  // person the row is addressed to, which is precisely when this badge is
  // wrong. That replaces the 60s poll outright; what is left is the uniform
  // degraded fallback — five minutes, and only while the stream is unavailable
  // or in error.
  useLiveUpdates(NOTIFICATION_EVENT_MAP);
  const refetchInterval = useSseFallbackInterval();
  const feed = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list({ pageSize: 20 }),
    refetchInterval,
  });

  // Both mutations update the cached feed directly instead of invalidating
  // it — a single row flipping to read shouldn't force a refetch of the
  // whole list. `onMutate` flips the row (and the badge) the instant the
  // click happens; `onError` rolls back to the exact snapshot taken before
  // the optimistic write, so a failed request leaves no trace once the
  // rollback lands. No settle-time invalidation on success: both endpoints
  // already return the server-computed `unread` count in their response
  // (`{ marked, unread }`), which `onSuccess` writes straight into the
  // cache — that's the one field the optimistic update can't compute
  // locally with full confidence, and refetching the whole feed to get it
  // would be exactly the round trip this change removes.
  const markRead = useMutation({
    mutationFn: (id) => notificationsApi.markRead(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['notifications'] });
      const previous = queryClient.getQueryData(['notifications']);
      queryClient.setQueryData(['notifications'], (old) => {
        if (!old) return old;
        const target = old.items?.find((item) => item.id === id);
        if (!target?.isUnread) return old;
        return {
          ...old,
          unread: Math.max(0, (old.unread ?? 0) - 1),
          items: old.items.map((item) =>
            item.id === id ? { ...item, isUnread: false } : item
          ),
        };
      });
      return { previous };
    },
    onError: (error, id, context) => {
      if (context?.previous) queryClient.setQueryData(['notifications'], context.previous);
    },
    onSuccess: (result) => {
      queryClient.setQueryData(['notifications'], (old) =>
        old ? { ...old, unread: result.unread } : old
      );
    },
  });
  const markAll = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['notifications'] });
      const previous = queryClient.getQueryData(['notifications']);
      queryClient.setQueryData(['notifications'], (old) =>
        old
          ? {
              ...old,
              unread: 0,
              items: old.items.map((item) => ({ ...item, isUnread: false })),
            }
          : old
      );
      return { previous };
    },
    onError: (error, variables, context) => {
      if (context?.previous) queryClient.setQueryData(['notifications'], context.previous);
    },
    onSuccess: (result) => {
      queryClient.setQueryData(['notifications'], (old) =>
        old ? { ...old, unread: result.unread } : old
      );
    },
  });

  // Click-away and Escape both close; a dropdown that only closes on its own
  // button is a dropdown that covers the page.
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) setOpen(false);
    };
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const unread = feed.data?.unread ?? 0;
  const items = feed.data?.items ?? [];

  const openItem = (item) => {
    if (item.isUnread) markRead.mutate(item.id);
    setOpen(false);
    // Not `item.url` directly. Several notification kinds are addressed to
    // admins *and* managers and spell their url `/admin/…`, because SQL cannot
    // know who will read it — see `portalNotificationUrl`. Navigating to the
    // literal value bounces a manager silently back to their own overview,
    // which reads as a click that did nothing.
    if (item.url) navigate(portalNotificationUrl(item.url, currentUser?.portal));
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="relative rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-50"
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-[70] mt-2 w-80 overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <p className="text-xs font-extrabold uppercase tracking-wider text-slate-500">
              Notifications
            </p>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markAll.mutate()}
                className="flex items-center gap-1 text-[11px] font-bold text-indigo-600 hover:text-indigo-700"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {feed.isLoading ? (
              <p className="px-4 py-6 text-center text-xs font-semibold text-slate-400">Loading…</p>
            ) : feed.error ? (
              <p role="alert" className="px-4 py-6 text-center text-xs font-semibold text-rose-600">
                {feed.error.message}
              </p>
            ) : items.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <Inbox className="mx-auto h-5 w-5 text-slate-300" />
                <p className="mt-2 text-xs font-semibold text-slate-400">Nothing yet.</p>
              </div>
            ) : (
              items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => openItem(item)}
                  className={`block w-full border-b border-slate-50 px-4 py-3 text-left transition-colors hover:bg-slate-50 ${
                    item.isUnread ? 'bg-indigo-50/40' : ''
                  }`}
                >
                  <span className="flex items-start gap-2">
                    {item.isUnread && (
                      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-500" />
                    )}
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-bold text-slate-800">
                        {item.title}
                      </span>
                      {item.body && (
                        <span className="mt-0.5 block text-[11px] font-medium leading-relaxed text-slate-500 line-clamp-2">
                          {item.body}
                        </span>
                      )}
                      <span className="mt-1 block text-[10px] font-semibold text-slate-400">
                        {when(item.createdAt)}
                      </span>
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
