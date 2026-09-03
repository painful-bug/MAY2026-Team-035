import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { securityApi } from '../../features/security/securityApi';
import { QUERY_POLICIES, PAGINATED } from '../../lib/api/queryClient';
import {
  Empty,
  ErrorText,
  GateModal,
  Loading,
  PageHeading,
  Pill,
  TabBar,
} from '../../features/security/components/Primitives';
import {
  SHIFT_STATUS_STYLES,
  inputClass,
  labelClass,
  shortDateTime,
  toLocalInput,
} from '../../features/security/components/vocabulary';

// The security manager's two lists: who is on when, and where the posts are.
//
// Everything here needs the `gate_admin` predicate — an admin or manager
// membership, or a `security` membership ranked manager/supervisor. A plain
// guard reaching this screen sees each card's own 403 rather than a blank page,
// which is the honest failure: they can read the roster, they just cannot
// change it.

const TABS = [
  ['shifts', 'Shifts'],
  ['posts', 'Posts'],
];

export default function Roster() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const tab = TABS.some(([id]) => id === tabParam) ? tabParam : 'shifts';
  const setTab = (next) =>
    setSearchParams(
      (params) => {
        const copy = new URLSearchParams(params);
        copy.set('tab', next);
        return copy;
      },
      { replace: true }
    );

  return (
    <div className="space-y-6">
      <PageHeading
        title="Roster"
        description="Put guards on posts, and keep the list of posts current."
      />
      <TabBar tabs={TABS} active={tab} onChange={setTab} />
      {tab === 'shifts' ? <Shifts /> : <Posts />}
    </div>
  );
}

// --------------------------------------------------------------------------
// Shifts
// --------------------------------------------------------------------------

function Shifts() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);

  // A fortnight forward from the start of today. The server caps at 200 rows
  // and matches on overlap, so a night shift straddling midnight still appears.
  const { from, to } = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setDate(end.getDate() + 14);
    return { from: start.toISOString(), to: end.toISOString() };
  }, []);

  const shifts = useQuery({
    queryKey: ['security', 'shifts', { from, to }],
    queryFn: () => securityApi.shifts({ from, to }),
    ...QUERY_POLICIES.list,
  });
  const posts = useQuery({
    queryKey: ['security', 'posts', {}],
    queryFn: () => securityApi.posts(),
    ...QUERY_POLICIES.list,
  });
  const roster = useQuery({
    queryKey: ['security', 'roster'],
    queryFn: () => securityApi.roster(),
    ...QUERY_POLICIES.list,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['security', 'shifts'] });

  const create = useMutation({
    mutationFn: (payload) => securityApi.createShift(payload),
    onSuccess: () => {
      setCreating(false);
      invalidate();
    },
  });

  const update = useMutation({
    mutationFn: ({ shiftId, payload }) => securityApi.updateShift(shiftId, payload),
    onSuccess: invalidate,
  });

  const rows = shifts.data || [];

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold text-slate-400">
          The next fortnight. A guard cannot hold two shifts at once — the overlap is refused by
          name.
        </p>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100"
        >
          <Plus className="h-4 w-4" />
          Schedule a shift
        </button>
      </div>

      <ErrorText error={shifts.error} />
      <ErrorText error={update.error} />
      {shifts.isPending ? <Loading /> : null}
      {!shifts.isPending && !shifts.error && rows.length === 0 ? (
        <Empty>Nothing on the roster for the next fortnight.</Empty>
      ) : null}

      <div className="space-y-3">
        {rows.map((shift) => (
          <article
            key={shift.id}
            className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Pill className={SHIFT_STATUS_STYLES[shift.status]}>{shift.status}</Pill>
                  <span className="text-xs font-bold text-slate-800">
                    {shift.guardName || 'Guard not named'}
                  </span>
                  {shift.guardRank && shift.guardRank !== 'member' ? (
                    <Pill className="bg-indigo-100 text-indigo-700">{shift.guardRank}</Pill>
                  ) : null}
                </div>
                <p className="mt-2 text-sm font-bold text-slate-900">
                  {shortDateTime(shift.startsAt)} — {shortDateTime(shift.endsAt)}
                </p>
                <p className="mt-1 text-[11px] font-semibold text-slate-400">
                  {shift.postName || 'Post not set'}
                  {shift.guardPhoneE164 ? ` · ${shift.guardPhoneE164}` : ''}
                </p>
                {shift.notes ? (
                  <p className="mt-1 text-[11px] font-semibold text-slate-500">{shift.notes}</p>
                ) : null}
              </div>

              {['scheduled', 'active'].includes(shift.status) ? (
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    disabled={update.isPending}
                    onClick={() =>
                      update.mutate({ shiftId: shift.id, payload: { status: 'missed' } })
                    }
                    className="rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                  >
                    Mark missed
                  </button>
                  <button
                    type="button"
                    disabled={update.isPending}
                    onClick={() =>
                      update.mutate({ shiftId: shift.id, payload: { status: 'cancelled' } })
                    }
                    className="rounded-xl border border-rose-200 px-3 py-2 text-[11px] font-bold text-rose-700 hover:bg-rose-50 disabled:opacity-60"
                  >
                    Cancel
                  </button>
                </div>
              ) : null}
            </div>
          </article>
        ))}
      </div>

      {creating ? (
        <ShiftForm
          posts={posts.data || []}
          roster={roster.data || []}
          rosterError={roster.error}
          onClose={() => setCreating(false)}
          onSubmit={(payload) => create.mutate(payload)}
          pending={create.isPending}
          error={create.error}
        />
      ) : null}
    </section>
  );
}

function ShiftForm({ posts, roster, rosterError, onClose, onSubmit, pending, error }) {
  const defaults = useMemo(() => {
    const start = new Date();
    start.setMinutes(0, 0, 0);
    start.setHours(start.getHours() + 1);
    const end = new Date(start);
    end.setHours(end.getHours() + 8);
    return { startsAt: toLocalInput(start), endsAt: toLocalInput(end) };
  }, []);

  const [form, setForm] = useState({
    staffAssignmentId: '',
    postId: '',
    notes: '',
    ...defaults,
  });
  const set = (key) => (event) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <GateModal
      title="Schedule a shift"
      description="The guard is notified as soon as you save."
      onClose={onClose}
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit({
            staffAssignmentId: form.staffAssignmentId,
            postId: form.postId || undefined,
            startsAt: new Date(form.startsAt).toISOString(),
            endsAt: new Date(form.endsAt).toISOString(),
            notes: form.notes.trim() || undefined,
          });
        }}
      >
        <div>
          <label className={labelClass} htmlFor="shift-guard">
            Guard
          </label>
          <select
            id="shift-guard"
            required
            value={form.staffAssignmentId}
            onChange={set('staffAssignmentId')}
            className={`${inputClass} mt-1`}
          >
            <option value="">Choose a guard…</option>
            {roster.map((entry) => (
              <option key={entry.staffAssignmentId} value={entry.staffAssignmentId}>
                {entry.name}
                {entry.jobTitle ? ` — ${entry.jobTitle}` : ''}
                {entry.shift ? ` (${entry.shift})` : ''}
              </option>
            ))}
          </select>
          <ErrorText error={rosterError} />
          {!rosterError && roster.length === 0 ? (
            <p className="mt-1 text-[11px] font-semibold text-slate-400">
              No active staff in a security department yet. Hire them from the admin portal
              first.
            </p>
          ) : null}
        </div>

        <div>
          <label className={labelClass} htmlFor="shift-post">
            Post
          </label>
          <select
            id="shift-post"
            value={form.postId}
            onChange={set('postId')}
            className={`${inputClass} mt-1`}
          >
            <option value="">No post</option>
            {posts.map((post) => (
              <option key={post.id} value={post.id}>
                {post.name}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass} htmlFor="shift-starts">
              Starts
            </label>
            <input
              id="shift-starts"
              type="datetime-local"
              required
              value={form.startsAt}
              onChange={set('startsAt')}
              className={`${inputClass} mt-1`}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="shift-ends">
              Ends
            </label>
            <input
              id="shift-ends"
              type="datetime-local"
              required
              value={form.endsAt}
              onChange={set('endsAt')}
              className={`${inputClass} mt-1`}
            />
          </div>
        </div>

        <div>
          <label className={labelClass} htmlFor="shift-notes">
            Notes
          </label>
          <textarea
            id="shift-notes"
            rows={3}
            maxLength={500}
            value={form.notes}
            onChange={set('notes')}
            placeholder="Handover at 06:00"
            className={`${inputClass} mt-1`}
          />
        </div>

        <ErrorText error={error} />

        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={pending}
            className="flex-1 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
          >
            {pending ? 'Scheduling…' : 'Schedule'}
          </button>
        </div>
      </form>
    </GateModal>
  );
}

// --------------------------------------------------------------------------
// Posts
// --------------------------------------------------------------------------

function Posts() {
  const queryClient = useQueryClient();
  const [includeInactive, setIncludeInactive] = useState(false);
  const [editing, setEditing] = useState(null); // null | {} | post

  const posts = useQuery({
    queryKey: ['security', 'posts', { includeInactive }],
    queryFn: () => securityApi.posts(includeInactive ? { includeInactive: true } : {}),
    ...QUERY_POLICIES.list,
    ...PAGINATED,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['security', 'posts'] });

  const save = useMutation({
    mutationFn: ({ postId, payload }) =>
      postId ? securityApi.updatePost(postId, payload) : securityApi.createPost(payload),
    onSuccess: () => {
      setEditing(null);
      invalidate();
    },
  });

  const rows = posts.data || [];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="inline-flex items-center gap-2 text-xs font-bold text-slate-600">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(event) => setIncludeInactive(event.target.checked)}
            className="h-4 w-4 rounded border-slate-300"
          />
          Show retired posts
        </label>
        <button
          type="button"
          onClick={() => setEditing({})}
          className="ml-auto inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100"
        >
          <Plus className="h-4 w-4" />
          Add a post
        </button>
      </div>

      <ErrorText error={posts.error} />
      {posts.isPending ? <Loading /> : null}
      {!posts.isPending && !posts.error && rows.length === 0 ? (
        <Empty>No posts defined yet.</Empty>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        {rows.map((post) => (
          <article
            key={post.id}
            className="flex items-start justify-between gap-3 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="truncate text-sm font-bold text-slate-900">{post.name}</p>
                {!post.isActive ? (
                  <Pill className="bg-slate-100 text-slate-500">Retired</Pill>
                ) : null}
              </div>
              {post.locationText ? (
                <p className="mt-1 text-[11px] font-semibold text-slate-400">
                  {post.locationText}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => setEditing(post)}
              className="shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-600 hover:bg-slate-50"
            >
              Edit
            </button>
          </article>
        ))}
      </div>

      {editing ? (
        <PostForm
          post={editing}
          onClose={() => setEditing(null)}
          onSubmit={(payload) => save.mutate({ postId: editing.id, payload })}
          pending={save.isPending}
          error={save.error}
        />
      ) : null}
    </section>
  );
}

function PostForm({ post, onClose, onSubmit, pending, error }) {
  const [form, setForm] = useState({
    name: post.name || '',
    locationText: post.locationText || '',
    isActive: post.id ? post.isActive : true,
  });

  return (
    <GateModal
      title={post.id ? 'Edit post' : 'Add a post'}
      description="A post is retired rather than deleted — old register entries still name it."
      onClose={onClose}
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit({
            name: form.name.trim(),
            locationText: form.locationText.trim() || undefined,
            isActive: form.isActive,
          });
        }}
      >
        <div>
          <label className={labelClass} htmlFor="post-name">
            Name
          </label>
          <input
            id="post-name"
            required
            maxLength={120}
            value={form.name}
            onChange={(event) => setForm((c) => ({ ...c, name: event.target.value }))}
            placeholder="Main Gate"
            className={`${inputClass} mt-1`}
          />
        </div>

        <div>
          <label className={labelClass} htmlFor="post-location">
            Where
          </label>
          <input
            id="post-location"
            maxLength={200}
            value={form.locationText}
            onChange={(event) => setForm((c) => ({ ...c, locationText: event.target.value }))}
            className={`${inputClass} mt-1`}
          />
        </div>

        <label className="flex items-center gap-2 text-xs font-bold text-slate-600">
          <input
            type="checkbox"
            checked={form.isActive}
            onChange={(event) => setForm((c) => ({ ...c, isActive: event.target.checked }))}
            className="h-4 w-4 rounded border-slate-300"
          />
          In use
        </label>

        <ErrorText error={error} />

        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={pending}
            className="flex-1 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
          >
            {pending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </GateModal>
  );
}
