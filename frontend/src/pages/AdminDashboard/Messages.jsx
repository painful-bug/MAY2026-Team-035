import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MessageSquare, Send } from 'lucide-react';
import { QUERY_POLICIES } from '../../lib/api/queryClient';
import { hiringApi } from '../../features/hiring/hiringApi';

// The department's side of the hiring conversation.
//
// The mirror of the worker portal's Messages screen, and deliberately the same
// shape — one thread per (department, provider) pair, chosen by the database's
// unique constraint rather than by either screen, so there is no "start a
// thread" step and no way to end up with two.
//
// The URL matters. `0041`'s notification for this side carries
// `url: '/admin/messages?conversation=<id>'`, so a click on the bell has to open
// the right thread. That is why the selected thread lives in a search parameter
// and not in component state: state cannot be linked to.
//
// No unread badge, for the same reason the worker screen has none: `0038`
// shipped no read receipts, and a badge would mean inventing them.

function Bubble({ message, mine }) {
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-xs font-semibold ${
          mine ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.body}</p>
        <p className={`mt-1 text-[10px] font-bold ${mine ? 'text-indigo-200' : 'text-slate-400'}`}>
          {message.authorName || (mine ? 'You' : 'Service partner')}
        </p>
      </div>
    </div>
  );
}

export default function Messages() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get('conversation');
  const [draft, setDraft] = useState('');
  const endRef = useRef(null);

  const threads = useQuery({
    queryKey: ['conversations'],
    queryFn: () => hiringApi.conversations(),
    ...QUERY_POLICIES.list,
  });
  const thread = useQuery({
    queryKey: ['conversations', selectedId],
    queryFn: () => hiringApi.conversation(selectedId),
    ...QUERY_POLICIES.detail,
    enabled: Boolean(selectedId),
  });

  const send = useMutation({
    mutationFn: (body) => hiringApi.sendMessage(selectedId, body),
    onSuccess: () => {
      setDraft('');
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    },
  });

  // Newest message in view on open and after every send. A chat that opens at
  // the top makes the reader scroll to find out what they were notified about.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' });
  }, [thread.data]);

  const items = threads.data || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Messages</h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          Hiring conversations with service partners.
        </p>
      </div>

      {threads.isLoading ? (
        <p className="text-sm font-semibold text-slate-500">Loading…</p>
      ) : threads.error ? (
        <p role="alert" className="text-sm font-semibold text-rose-600">{threads.error.message}</p>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-slate-100 bg-white p-12 text-center shadow-sm">
          <MessageSquare className="mx-auto h-6 w-6 text-slate-300" />
          <p className="mt-3 text-sm font-bold text-slate-700">No conversations yet</p>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            A thread opens the first time you or a service partner writes about an application.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[20rem_1fr]">
          <div className="space-y-2">
            {items.map((entry) => (
              <button
                key={entry.id}
                type="button"
                onClick={() => setSearchParams({ conversation: entry.id })}
                className={`w-full rounded-2xl border p-4 text-left ${
                  entry.id === selectedId
                    ? 'border-indigo-200 bg-indigo-50/50'
                    : 'border-slate-100 bg-white'
                }`}
              >
                <p className="font-extrabold text-slate-800">
                  {entry.providerDisplayName || 'Service partner'}
                </p>
                <p className="mt-0.5 text-[11px] font-bold text-slate-400">
                  {entry.departmentName || 'Department'}
                </p>
                {/* The list carries `lastMessageBody` so a preview costs no
                    request per thread. */}
                {entry.lastMessageBody ? (
                  <p className="mt-1.5 truncate text-[11px] font-semibold text-slate-500">
                    {entry.lastMessageBody}
                  </p>
                ) : null}
              </button>
            ))}
          </div>

          <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
            {!selectedId ? (
              <p className="py-12 text-center text-sm font-bold text-slate-400">
                Pick a conversation.
              </p>
            ) : thread.isLoading ? (
              <p className="text-sm font-semibold text-slate-500">Loading…</p>
            ) : thread.error ? (
              <p role="alert" className="text-sm font-semibold text-rose-600">
                {thread.error.message}
              </p>
            ) : (
              <>
                <div className="max-h-[26rem] space-y-3 overflow-y-auto pb-4">
                  {(thread.data?.messages || []).map((message) => (
                    // `authorSide` is decided by the row, not by the caller: the
                    // thread knows which side wrote each message even when the
                    // provider has since been hired and holds a membership that
                    // would be an equally true answer.
                    <Bubble
                      key={message.id}
                      message={message}
                      mine={message.authorSide !== 'provider'}
                    />
                  ))}
                  <div ref={endRef} />
                </div>

                <form
                  className="flex gap-2 border-t border-slate-50 pt-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (draft.trim()) send.mutate(draft.trim());
                  }}
                >
                  <input
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                    value={draft}
                    maxLength={4000}
                    placeholder="Write a message"
                    onChange={(event) => setDraft(event.target.value)}
                  />
                  <button
                    type="submit"
                    disabled={send.isPending || !draft.trim()}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
                  >
                    <Send className="h-4 w-4" />Send
                  </button>
                </form>
                {send.error ? (
                  <p role="alert" className="mt-2 text-xs font-semibold text-rose-600">
                    {send.error.message}
                  </p>
                ) : null}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
