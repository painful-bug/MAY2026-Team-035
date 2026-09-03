import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { QUERY_POLICIES } from '../../lib/api/queryClient';
import { ChevronLeft, MessageSquare, Send } from 'lucide-react';
import { workerApi } from '../../features/worker/workerApi';
import { communityColor } from '../../lib/communityColor';
import { holdsLeadershipEngagement } from '../../lib/staffVocabulary';

const stamp = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });

// The hiring thread, from the provider's end. One thread per (department,
// provider) — the unique constraint in `0038` is the whole concurrency story,
// so there is no "start a thread" button here: a department opens it, and the
// provider answers.
//
// **The open thread lives in the URL, not in state.** `0041:611` notifies the
// provider with `url: '/worker/messages?conversation=<id>'`, and until
// 2026-08-11 this screen kept the selection in `useState` — so the bell landed
// the worker on a thread list with nothing opened and no clue which of the rows
// the message had been about. State cannot be linked to. The admin twin
// (`AdminDashboard/Messages.jsx`) got this right the day it was written; this
// side simply never had it, which is the kind of gap only a per-parameter
// inventory finds, because the link itself works.
//
// Opening a thread is a real history entry on purpose: on the phone this screen
// is built for, that makes the hardware back button close the thread instead of
// leaving the portal.
//
// No unread badge. `0038` shipped with no read receipts on purpose, and
// `WorkerSnapshot` says so in print rather than inventing a count. A badge here
// would mean inventing the receipts underneath it.
//
// And no supervisors (amendment 3, ruling B1). This is the marketplace HIRING
// inbox — a department courting a provider — and leadership was hired by an
// administrator typing their email, so no department ever opens a thread at
// them. A deep link gets the refusal in words; their conversations are the
// complaint chats in the floating Messages dock.

export default function WorkerMessages() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const openId = searchParams.get('conversation');
  const [draft, setDraft] = useState('');
  const bottom = useRef(null);

  const snapshot = useQuery({
    queryKey: ['worker-snapshot'],
    queryFn: workerApi.snapshot,
    ...QUERY_POLICIES.snapshot,
  });
  const leadership = holdsLeadershipEngagement(snapshot.data?.communities);
  const threads = useQuery({
    queryKey: ['worker-conversations'],
    queryFn: workerApi.conversations,
    ...QUERY_POLICIES.list,
    enabled: snapshot.isSuccess && !leadership,
  });
  const thread = useQuery({
    queryKey: ['worker-conversation', openId],
    queryFn: () => workerApi.conversation(openId),
    ...QUERY_POLICIES.detail,
    enabled: Boolean(openId) && snapshot.isSuccess && !leadership,
  });

  const send = useMutation({
    mutationFn: () => workerApi.sendMessage(openId, draft.trim()),
    onSuccess: () => {
      setDraft('');
      void queryClient.invalidateQueries({ queryKey: ['worker-conversation', openId] });
      void queryClient.invalidateQueries({ queryKey: ['worker-conversations'] });
    },
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' });
  }, [thread.data]);

  const rows = threads.data ?? [];

  if (snapshot.isLoading) {
    return <p className="text-xs font-semibold text-slate-400">Loading…</p>;
  }

  if (leadership) {
    return (
      <p className="rounded-2xl border border-slate-100 bg-white p-6 text-xs font-semibold text-slate-500">
        These are hiring conversations — a department talking terms with a
        marketplace professional, and nobody courts somebody already on the
        payroll. Your conversations live in the floating Messages dock at the
        corner of the screen.
      </p>
    );
  }

  if (openId) {
    const conversation = thread.data?.conversation;
    const colour = communityColor(conversation?.communityId);
    return (
      <div className="flex h-[calc(100vh-9rem)] flex-col rounded-3xl border border-slate-200 bg-white">
        <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
          <button
            type="button"
            aria-label="Back to threads"
            onClick={() => setSearchParams({})}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <div className="min-w-0">
            <p className="truncate text-sm font-extrabold text-slate-900">{conversation?.departmentName || 'Department'}</p>
            <p className="flex items-center gap-1.5 truncate text-xs font-semibold text-slate-500">
              <span className={`h-1.5 w-1.5 rounded-full ${colour.dot}`} />
              {conversation?.communityName}
            </p>
          </div>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {thread.isPending && <p className="text-center text-sm font-semibold text-slate-400">Loading…</p>}
          {/* Reachable only now that the id can arrive from a link: a thread
              that has been closed, or one belonging to another account, used to
              be unaskable because you could only click a row you could see.
              Without this branch it renders as a blank thread under a real
              header, which reads as "no messages" rather than as an error. */}
          {thread.isError && (
            <p role="alert" className="py-10 text-center text-sm font-semibold text-rose-700">
              {thread.error?.message || 'That conversation is no longer open to you.'}
            </p>
          )}
          {(thread.data?.messages ?? []).map((message) => {
            const mine = message.authorSide === 'provider';
            return (
              <div key={message.id} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 ${
                    mine ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-800'
                  }`}
                >
                  {!mine && <p className="mb-0.5 text-[10px] font-bold opacity-70">{message.authorName}</p>}
                  <p className="whitespace-pre-line text-sm font-medium">{message.body}</p>
                  <p className={`mt-1 text-[10px] font-semibold ${mine ? 'text-indigo-200' : 'text-slate-400'}`}>
                    {message.createdAt ? stamp.format(new Date(message.createdAt)) : ''}
                  </p>
                </div>
              </div>
            );
          })}
          {thread.isSuccess && (thread.data?.messages ?? []).length === 0 && (
            <p className="py-10 text-center text-sm font-semibold text-slate-400">No messages yet. Say hello.</p>
          )}
          <div ref={bottom} />
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.trim()) send.mutate();
          }}
          className="flex items-end gap-2 border-t border-slate-100 p-3"
        >
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={1}
            maxLength={4000}
            placeholder="Write a message"
            className="max-h-32 flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium outline-none focus:border-indigo-400"
          />
          <button
            type="submit"
            aria-label="Send"
            disabled={send.isPending || !draft.trim()}
            className="rounded-xl bg-indigo-600 p-2.5 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
        {send.isError && (
          <p className="px-4 pb-3 text-xs font-semibold text-rose-700">{send.error?.message || 'Could not send.'}</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold text-slate-900">Messages</h1>

      {threads.isPending && <p className="py-10 text-center text-sm font-semibold text-slate-400">Loading…</p>}

      {threads.isSuccess && rows.length === 0 && (
        <div className="rounded-3xl border border-dashed border-slate-300 px-6 py-12 text-center">
          <MessageSquare className="mx-auto h-10 w-10 text-slate-300" />
          <p className="mt-4 text-base font-extrabold text-slate-800">No conversations yet</p>
          <p className="mx-auto mt-1 max-w-md text-sm font-medium text-slate-500">
            A department manager opens the thread when they want to talk terms. Yours will appear here.
          </p>
        </div>
      )}

      <div className="space-y-2">
        {rows.map((conversation) => {
          const colour = communityColor(conversation.communityId);
          return (
            <button
              key={conversation.id}
              type="button"
              onClick={() => setSearchParams({ conversation: conversation.id })}
              className={`w-full rounded-2xl border border-l-4 border-slate-200 bg-white p-4 text-left hover:shadow-md ${colour.bar}`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <p className="truncate text-sm font-extrabold text-slate-900">{conversation.departmentName}</p>
                <span className="shrink-0 text-[10px] font-semibold text-slate-400">
                  {conversation.lastMessageAt ? stamp.format(new Date(conversation.lastMessageAt)) : ''}
                </span>
              </div>
              <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs font-semibold text-slate-500">
                <span className={`h-1.5 w-1.5 rounded-full ${colour.dot}`} />
                {conversation.communityName}
              </p>
              {conversation.lastMessageBody && (
                <p className="mt-1.5 truncate text-xs font-medium text-slate-600">{conversation.lastMessageBody}</p>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
