import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Lock,
  MessageCircle,
  PenSquare,
  Send,
  X,
} from 'lucide-react';
import { messagesApi } from '../../features/messages/messagesApi';
import { useAuthStore } from '../../store/authStore';

// The floating chat dock — mounted once in App.jsx, outside <Routes>, so
// every portal gets it (admin, worker, security, security-manager, resident:
// the PO's "all of them"). Three views in one panel: the mailbox, a thread,
// and New message, whose "to" list is GET /messages/recipients — department
// colleagues, managers, and the admins who ARE the committee.
//
// A locked thread (a work-order channel whose job ended) renders its history
// with the composer replaced by a lock notice; the 409 behind it is the
// product rule, not an error state.
//
// Unread is a last-seen stamp in localStorage, deliberately: a read-receipt
// model is a schema and a policy, and a dot that clears when you open the
// dock is what the screen actually needs.

const SEEN_KEY = 'hb-chat-seen-at';

function when(iso) {
  if (!iso) return '';
  const then = new Date(iso);
  const minutes = Math.round((Date.now() - then.getTime()) / 60_000);
  if (minutes < 1) return 'now';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return then.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

function ThreadListView({ threads, onOpen, onCompose }) {
  return (
    <>
      <div className="flex-1 overflow-y-auto">
        {threads.isLoading ? (
          <p className="px-4 py-6 text-center text-xs font-semibold text-slate-400">Loading…</p>
        ) : threads.error ? (
          <p role="alert" className="px-4 py-6 text-center text-xs font-semibold text-rose-600">
            {threads.error.message}
          </p>
        ) : (threads.data || []).length === 0 ? (
          <p className="px-4 py-8 text-center text-xs font-semibold text-slate-400">
            No conversations yet.
          </p>
        ) : (
          (threads.data || []).map((thread) => (
            <button
              key={thread.id}
              type="button"
              onClick={() => onOpen(thread.id)}
              className="block w-full border-b border-slate-50 px-4 py-3 text-left hover:bg-slate-50"
            >
              <span className="flex items-center gap-2">
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate text-xs font-extrabold text-slate-800">
                      {thread.counterpartName}
                    </span>
                    {thread.lockedAt ? <Lock className="h-3 w-3 text-slate-400" /> : null}
                  </span>
                  <span className="block truncate text-[11px] font-medium text-slate-500">
                    {thread.lastMessageBody || (thread.kind === 'work_order' ? 'About a job' : 'New conversation')}
                  </span>
                </span>
                <span className="shrink-0 text-[10px] font-semibold text-slate-400">
                  {when(thread.lastMessageAt)}
                </span>
              </span>
            </button>
          ))
        )}
      </div>
      <div className="border-t border-slate-100 p-3">
        <button
          type="button"
          onClick={onCompose}
          className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-indigo-600 py-2.5 text-xs font-bold text-white hover:bg-indigo-700"
        >
          <PenSquare className="h-3.5 w-3.5" />New message
        </button>
      </div>
    </>
  );
}

function ComposeView({ communities, initialCommunityId, onOpened, onBack }) {
  const [communityId, setCommunityId] = useState(initialCommunityId || communities[0]?.id || '');
  const [query, setQuery] = useState('');

  const recipients = useQuery({
    queryKey: ['dm-recipients', communityId],
    queryFn: () => messagesApi.recipients(communityId),
    enabled: Boolean(communityId),
  });
  const open = useMutation({
    mutationFn: (recipientProfileId) =>
      messagesApi.openThread({ communityId, recipientProfileId }),
    onSuccess: (thread) => onOpened(thread),
  });

  const matches = (recipients.data || []).filter((person) =>
    person.displayName.toLowerCase().includes(query.trim().toLowerCase())
  );

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="space-y-2 border-b border-slate-100 p-3">
        {communities.length > 1 ? (
          <select
            value={communityId}
            onChange={(event) => setCommunityId(event.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:outline-none"
          >
            {communities.map((community) => (
              <option key={community.id} value={community.id}>{community.name}</option>
            ))}
          </select>
        ) : null}
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="To: start typing a name…"
          className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        {!communityId ? (
          <p className="px-4 py-6 text-center text-xs font-semibold text-slate-400">
            Open a conversation from a community screen first.
          </p>
        ) : recipients.isLoading ? (
          <p className="px-4 py-6 text-center text-xs font-semibold text-slate-400">Loading…</p>
        ) : recipients.error ? (
          <p role="alert" className="px-4 py-6 text-center text-xs font-semibold text-rose-600">
            {recipients.error.message}
          </p>
        ) : matches.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs font-semibold text-slate-400">
            Nobody you can message matches.
          </p>
        ) : (
          matches.map((person) => (
            <button
              key={person.profileId}
              type="button"
              disabled={open.isPending}
              onClick={() => open.mutate(person.profileId)}
              className="block w-full border-b border-slate-50 px-4 py-3 text-left hover:bg-slate-50 disabled:opacity-60"
            >
              <span className="block text-xs font-extrabold text-slate-800">{person.displayName}</span>
              <span className="block text-[10px] font-semibold text-slate-400">{person.label}</span>
            </button>
          ))
        )}
        {open.error ? (
          <p role="alert" className="px-4 py-2 text-xs font-semibold text-rose-600">
            {open.error.message}
          </p>
        ) : null}
      </div>
      <div className="border-t border-slate-100 p-3">
        <button
          type="button"
          onClick={onBack}
          className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
        >
          <ArrowLeft className="h-3.5 w-3.5" />Back
        </button>
      </div>
    </div>
  );
}

function ThreadView({ threadId, myProfileId, onBack }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState('');
  const endRef = useRef(null);

  const thread = useQuery({
    queryKey: ['dm-thread', threadId],
    queryFn: () => messagesApi.thread(threadId),
    refetchInterval: 20_000,
  });
  const send = useMutation({
    mutationFn: (body) => messagesApi.send(threadId, body),
    onSuccess: () => {
      setDraft('');
      queryClient.invalidateQueries({ queryKey: ['dm-thread', threadId] });
      queryClient.invalidateQueries({ queryKey: ['dm-threads'] });
    },
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' });
  }, [thread.data]);

  const data = thread.data;
  const locked = Boolean(data?.lockedAt);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2.5">
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-50"
          aria-label="Back to conversations"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="min-w-0">
          <p className="truncate text-xs font-extrabold text-slate-800">
            {data?.counterpartName || '…'}
          </p>
          <p className="truncate text-[10px] font-semibold text-slate-400">
            {data?.communityName}
            {data?.kind === 'work_order' ? ' · about a job' : ''}
          </p>
        </div>
        {locked ? <Lock className="ml-auto h-4 w-4 shrink-0 text-slate-400" /> : null}
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {(data?.messages || []).map((message) =>
          message.authorProfileId == null ? (
            // A system line: the database explaining a silence.
            <p key={message.id} className="text-center text-[10px] font-semibold text-slate-400">
              {message.body}
            </p>
          ) : (
            <div
              key={message.id}
              className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs font-medium ${
                message.authorProfileId === myProfileId
                  ? 'ml-auto rounded-br-sm bg-indigo-600 text-white'
                  : 'rounded-bl-sm bg-slate-100 text-slate-700'
              }`}
            >
              {message.body}
            </div>
          )
        )}
        <div ref={endRef} />
      </div>

      {locked ? (
        <p className="border-t border-slate-100 px-4 py-3 text-center text-[11px] font-bold text-slate-400">
          <Lock className="mr-1 inline h-3 w-3" />
          This conversation closed when the job ended.
        </p>
      ) : (
        <form
          className="flex items-end gap-2 border-t border-slate-100 p-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.trim()) send.mutate(draft.trim());
          }}
        >
          <textarea
            rows={1}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Write a message…"
            className="flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
          />
          <button
            type="submit"
            disabled={send.isPending || !draft.trim()}
            className="rounded-xl bg-indigo-600 p-2.5 text-white disabled:opacity-50"
            aria-label="Send"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      )}
      {send.error ? (
        <p role="alert" className="px-4 pb-2 text-[11px] font-semibold text-rose-600">
          {send.error.message}
        </p>
      ) : null}
    </div>
  );
}

export default function ChatDock() {
  const sessionContext = useAuthStore((state) => state.sessionContext);
  const [open, setOpen] = useState(false);
  // 'list' | 'compose' | a thread id.
  const [view, setView] = useState('list');
  const [composeCommunity, setComposeCommunity] = useState(null);
  const [seenAt, setSeenAt] = useState(() => localStorage.getItem(SEEN_KEY) || '');

  const signedIn = Boolean(sessionContext?.identity);
  const myProfileId = sessionContext?.identity?.id || sessionContext?.identity?.user_id || '';

  const threads = useQuery({
    queryKey: ['dm-threads'],
    queryFn: messagesApi.threads,
    enabled: signedIn,
    refetchInterval: open ? 30_000 : 90_000,
  });

  // Screens elsewhere (the employee page) ask the dock to open onto New
  // message for a community. An event, because the dock lives outside
  // <Routes> and its openers are scattered across portals.
  useEffect(() => {
    const onOpen = (event) => {
      setOpen(true);
      setComposeCommunity(event.detail?.communityId || null);
      setView(event.detail?.threadId || (event.detail?.communityId ? 'compose' : 'list'));
    };
    window.addEventListener('hb:chat-open', onOpen);
    return () => window.removeEventListener('hb:chat-open', onOpen);
  }, []);

  const communities = useMemo(() => {
    const map = new Map();
    const membership = sessionContext?.membership;
    if (membership?.community_id) {
      map.set(membership.community_id, {
        id: membership.community_id,
        name: membership.community_name || 'My community',
      });
    }
    for (const thread of threads.data || []) {
      if (!map.has(thread.communityId)) {
        map.set(thread.communityId, {
          id: thread.communityId,
          name: thread.communityName || 'Community',
        });
      }
    }
    if (composeCommunity && !map.has(composeCommunity)) {
      map.set(composeCommunity, { id: composeCommunity, name: 'This community' });
    }
    return [...map.values()];
  }, [sessionContext, threads.data, composeCommunity]);

  if (!signedIn) return null;

  const latest = (threads.data || []).reduce(
    (max, thread) => (thread.lastMessageAt && thread.lastMessageAt > max ? thread.lastMessageAt : max),
    ''
  );
  const hasUnseen = Boolean(latest && latest > seenAt);

  const openDock = () => {
    setOpen(true);
    if (latest) {
      localStorage.setItem(SEEN_KEY, latest);
      setSeenAt(latest);
    }
  };

  return (
    <>
      {open ? (
        <div className="fixed bottom-5 right-5 z-[900] flex h-[28rem] w-80 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <p className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-slate-500">
              <MessageCircle className="h-4 w-4 text-indigo-500" />Messages
            </p>
            <button
              type="button"
              onClick={() => { setOpen(false); setView('list'); }}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-50"
              aria-label="Close messages"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {view === 'list' ? (
            <ThreadListView
              threads={threads}
              onOpen={(id) => setView(id)}
              onCompose={() => setView('compose')}
            />
          ) : view === 'compose' ? (
            <ComposeView
              communities={communities}
              initialCommunityId={composeCommunity}
              onOpened={(thread) => setView(thread.id)}
              onBack={() => setView('list')}
            />
          ) : (
            <ThreadView threadId={view} myProfileId={myProfileId} onBack={() => setView('list')} />
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={openDock}
          className="fixed bottom-5 right-5 z-[900] flex h-12 w-12 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg shadow-indigo-200 hover:bg-indigo-700"
          aria-label="Open messages"
        >
          <MessageCircle className="h-5 w-5" />
          {hasUnseen ? (
            <span className="absolute right-1 top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-rose-500" />
          ) : null}
        </button>
      )}
    </>
  );
}
