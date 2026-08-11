import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Ban, Check, Clock, DoorOpen, Inbox, MapPin, MessageSquare, Search,
  Shuffle, UserMinus, UserPlus, X,
} from 'lucide-react';
import { hiringApi } from '../../features/hiring/hiringApi';
import { JOB_TITLES, SHIFTS, STAFF_RANKS, rankLabel } from '../../lib/staffVocabulary';

// The manager's side of hiring: who wants in, who could be asked, who is on.
//
// react-query against the live API, like PendingRegistrations.jsx and unlike the
// department pages it links back to -- those are the demo half, over zustand.
// The two coexist on purpose (§6.11 R1); nothing here migrates anything.
//
// Three tabs rather than three routes, because they are three views of one
// question and a manager moves between them in one sitting: somebody applies,
// you look for alternatives, you decide, you look at the roster you just
// changed. Same reasoning as the worker portal's Communities screen.

const TABS = [
  { id: 'applications', label: 'Applications', icon: Inbox },
  { id: 'candidates', label: 'Find people', icon: Search },
  { id: 'roster', label: 'Roster', icon: UserPlus },
  { id: 'departures', label: 'Departures', icon: DoorOpen },
];

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

// Both vocabularies live here: an application is `accepted`, a departure is
// `approved`. They are not the same word on purpose — one is a state something
// ends up in, the other an act somebody performs — so both are listed rather
// than one being mapped onto the other.
const STATUS_STYLES = {
  pending: 'bg-amber-50 text-amber-700',
  accepted: 'bg-emerald-50 text-emerald-700',
  approved: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-rose-50 text-rose-700',
  withdrawn: 'bg-slate-100 text-slate-500',
  cancelled: 'bg-slate-100 text-slate-500',
  expired: 'bg-slate-100 text-slate-500',
};

function Pill({ children, tone = 'bg-slate-100 text-slate-600' }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${tone}`}>
      {children}
    </span>
  );
}

function Empty({ children }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-12 text-center">
      <p className="text-sm font-bold text-slate-500">{children}</p>
    </div>
  );
}

function Distance({ km }) {
  if (km === null || km === undefined) return null;
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-slate-400">
      <MapPin className="h-3.5 w-3.5" />
      {km < 1 ? 'under 1 km' : `${km.toFixed(1)} km`}
    </span>
  );
}

// The terms a manager names at the moment they say yes.
//
// This form exists on an *application* and not on an invitation, and that is the
// API's shape rather than a layout choice: on an application nobody has offered
// terms yet, and on an invitation they are already in the row and `decide`
// ignores anything sent with the acceptance -- which is what stops a provider
// accepting themselves in as a manager.
function AcceptTerms({ onSubmit, onCancel, pending }) {
  const [rank, setRank] = useState('member');
  const [jobTitle, setJobTitle] = useState('');
  const [shift, setShift] = useState('Day');

  return (
    <form
      className="space-y-3 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({ rank, jobTitle: jobTitle.trim() || null, shift });
      }}
    >
      <p className="text-[11px] font-bold uppercase tracking-wide text-indigo-500">
        Terms on offer
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="space-y-1.5">
          <span className="text-[11px] font-bold text-slate-500">Rank</span>
          <select className={inputClass} value={rank} onChange={(e) => setRank(e.target.value)}>
            {STAFF_RANKS.map((entry) => (
              <option key={entry.value} value={entry.value}>{entry.label}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5">
          <span className="text-[11px] font-bold text-slate-500">Job title</span>
          {/* Free text with suggestions: `job_title` has no check constraint, so
              a closed list here would invent a rule the database does not have. */}
          <input
            className={inputClass}
            list="hb-job-titles"
            value={jobTitle}
            placeholder="Plumber"
            onChange={(e) => setJobTitle(e.target.value)}
          />
        </label>
        <label className="space-y-1.5">
          <span className="text-[11px] font-bold text-slate-500">Shift</span>
          <select className={inputClass} value={shift} onChange={(e) => setShift(e.target.value)}>
            {SHIFTS.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={pending}
          className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
        >
          <Check className="h-4 w-4" />Confirm hire
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function ApplicationCard({ application, onDecide, pending }) {
  const [accepting, setAccepting] = useState(false);
  const isPending = application.status === 'pending';
  const isInvitation = application.direction === 'invited';

  return (
    <article className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-extrabold text-slate-800">
            {application.providerDisplayName || 'Service partner'}
          </h3>
          <p className="text-xs font-semibold text-slate-400">
            {application.providerHeadline || 'No headline'}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <Pill tone={STATUS_STYLES[application.status]}>{application.status}</Pill>
          <Pill>{isInvitation ? 'we invited' : 'they applied'}</Pill>
        </div>
      </div>

      {application.providerSkillNames?.length ? (
        <div className="flex flex-wrap gap-1.5">
          {application.providerSkillNames.map((skill) => (
            <Pill key={skill} tone="bg-sky-50 text-sky-700">{skill}</Pill>
          ))}
        </div>
      ) : null}

      {application.message ? (
        <p className="rounded-xl bg-slate-50 p-3 text-xs font-semibold text-slate-600">
          “{application.message}”
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-slate-50 pt-3">
        <Distance km={application.distanceKm} />
        {application.providerPhoneE164 ? (
          <span className="text-[11px] font-bold text-slate-400">{application.providerPhoneE164}</span>
        ) : null}
        {application.rank ? (
          <span className="text-[11px] font-bold text-slate-400">
            {rankLabel(application.rank)}
            {application.jobTitle ? ` · ${application.jobTitle}` : ''}
            {application.shift ? ` · ${application.shift}` : ''}
          </span>
        ) : null}
      </div>

      {/* An invitation is ours to withdraw, not ours to accept -- only the
          provider can answer it, so the accept control is absent rather than
          disabled. A disabled button invites a manager to wonder what unlocks it. */}
      {isPending && !isInvitation ? (
        accepting ? (
          <AcceptTerms
            pending={pending}
            onCancel={() => setAccepting(false)}
            onSubmit={(terms) => onDecide(application.id, { decision: 'accepted', ...terms })}
          />
        ) : (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setAccepting(true)}
              disabled={pending}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-indigo-600 py-2.5 text-xs font-bold text-white disabled:opacity-60"
            >
              <Check className="h-4 w-4" />Accept
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={() => {
                const note = window.prompt('Reason for turning this application down (optional):');
                if (note === null) return;
                onDecide(application.id, { decision: 'rejected', note: note.trim() || null });
              }}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-60"
            >
              <X className="h-4 w-4" />Reject
            </button>
          </div>
        )
      ) : null}

      {isPending && isInvitation ? (
        <p className="text-[11px] font-semibold text-slate-400">
          Waiting on their answer. They have been notified.
        </p>
      ) : null}
    </article>
  );
}

function CandidateCard({ candidate, departmentId, onInvited }) {
  const [inviting, setInviting] = useState(false);
  const [rank, setRank] = useState('member');
  const [jobTitle, setJobTitle] = useState('');
  const [shift, setShift] = useState('Day');
  const [message, setMessage] = useState('');

  const invite = useMutation({
    mutationFn: () => hiringApi.invite(departmentId, {
      serviceProviderId: candidate.id,
      rank,
      jobTitle: jobTitle.trim() || null,
      shift,
      message: message.trim() || null,
    }),
    onSuccess: () => { setInviting(false); onInvited(); },
  });

  return (
    <article className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-extrabold text-slate-800">{candidate.displayName}</h3>
          <p className="text-xs font-semibold text-slate-400">
            {candidate.headline || 'No headline'}
          </p>
        </div>
        {candidate.isAvailable
          ? <Pill tone="bg-emerald-50 text-emerald-700">available</Pill>
          : <Pill>not taking work</Pill>}
      </div>

      {/* `matchingSkillNames` is why they are on this list; `skillNames` is
          everything they do. Showing only the second leaves a manager wondering
          why an electrician is being offered for a plumbing department. */}
      {candidate.matchingSkillNames?.length ? (
        <div className="space-y-1.5">
          <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">
            Matches this department
          </p>
          <div className="flex flex-wrap gap-1.5">
            {candidate.matchingSkillNames.map((skill) => (
              <Pill key={skill} tone="bg-indigo-50 text-indigo-700">{skill}</Pill>
            ))}
          </div>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-slate-50 pt-3">
        <Distance km={candidate.distanceKm} />
        <span className="text-[11px] font-bold text-slate-400">
          Works in {candidate.communityCount} {candidate.communityCount === 1 ? 'society' : 'societies'}
        </span>
      </div>

      {/* One open negotiation per pair is a unique index. A screen that always
          offered "Invite" would 409 on exactly the candidates a manager is most
          likely to click twice. */}
      {candidate.hasOpenApplication ? (
        <p className="text-[11px] font-semibold text-amber-600">
          Already in your applications tab.
        </p>
      ) : inviting ? (
        <form
          className="space-y-3 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4"
          onSubmit={(event) => { event.preventDefault(); invite.mutate(); }}
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <select className={inputClass} value={rank} onChange={(e) => setRank(e.target.value)}>
              {STAFF_RANKS.map((entry) => (
                <option key={entry.value} value={entry.value}>{entry.label}</option>
              ))}
            </select>
            <input
              className={inputClass}
              list="hb-job-titles"
              value={jobTitle}
              placeholder="Job title"
              onChange={(e) => setJobTitle(e.target.value)}
            />
            <select className={inputClass} value={shift} onChange={(e) => setShift(e.target.value)}>
              {SHIFTS.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </div>
          <textarea
            className={inputClass}
            rows={2}
            value={message}
            placeholder="A note with the invitation (optional)"
            onChange={(e) => setMessage(e.target.value)}
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={invite.isPending}
              className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
            >
              Send invitation
            </button>
            <button
              type="button"
              onClick={() => setInviting(false)}
              className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
            >
              Cancel
            </button>
          </div>
          {invite.error ? (
            <p role="alert" className="text-xs font-semibold text-rose-600">{invite.error.message}</p>
          ) : null}
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setInviting(true)}
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-indigo-600 py-2.5 text-xs font-bold text-white"
        >
          <UserPlus className="h-4 w-4" />Invite
        </button>
      )}
    </article>
  );
}

const whenText = (value) => {
  if (!value) return 'no time set';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'no time set'
    : date.toLocaleString(undefined, {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    });
};

const dayText = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? null
    : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
};

// One departure, and the work it would strand.
//
// Until 2026-08-10 the approve button was disabled while anything was booked.
// The PO overturned that: the decision is the manager's, and approval releases
// the conflicting work to the dispatch pool. The card approves at the
// *requested* date; picking a different date, checking coverage and the
// per-item handover live on the employee page this card links to.
function DepartureCard({ departure, departmentId, roster, onChanged }) {
  const [open, setOpen] = useState(false);
  const isPending = departure.status === 'pending';

  const detail = useQuery({
    queryKey: ['hiring', departmentId, 'departure', departure.id],
    queryFn: () => hiringApi.departure(departmentId, departure.id),
    enabled: open,
  });

  const reassign = useMutation({
    mutationFn: (payload) => hiringApi.reassign(departmentId, departure.id, payload),
    onSuccess: () => { detail.refetch(); onChanged(); },
  });
  const decide = useMutation({
    mutationFn: (payload) => hiringApi.decideDeparture(departmentId, departure.id, payload),
    onSuccess: onChanged,
  });

  // Anyone still on the roster except the person leaving. The database refuses
  // a successor who is not on this department's roster anyway; the filter is
  // here so the option never appears rather than so the write is safe.
  const successors = roster.filter(
    (member) => member.id !== departure.staffAssignmentId && member.status === 'active'
  );
  const left = departure.openCommitmentCount;

  return (
    <article className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link
            to={`/admin/departments/${departmentId}/staff/${departure.staffAssignmentId}?departure=${departure.id}`}
            className="font-extrabold text-slate-800 hover:text-indigo-700"
          >
            {departure.displayName}
          </Link>
          <p className="text-xs font-semibold text-slate-400">
            {rankLabel(departure.rank)}
            {departure.jobTitle ? ` · ${departure.jobTitle}` : ''}
          </p>
          <p className="mt-1 text-[11px] font-bold text-amber-700">
            {departure.status === 'approved' && departure.effectiveAt
              ? `Leaving ${dayText(departure.effectiveAt)}`
              : departure.requestedEffectiveAt
                ? `Wants to leave ${dayText(departure.requestedEffectiveAt)}`
                : 'Wants to leave immediately'}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <Pill tone={STATUS_STYLES[departure.status]}>{departure.status}</Pill>
          <Pill>{departure.initiatedBy === 'worker' ? 'they asked' : 'we started it'}</Pill>
        </div>
      </div>

      {departure.reason ? (
        <p className="rounded-xl bg-slate-50 p-3 text-xs font-semibold text-slate-600">
          “{departure.reason}”
        </p>
      ) : null}

      {isPending ? (
        <div className="flex items-center gap-2 border-t border-slate-50 pt-3">
          <Clock className="h-4 w-4 text-slate-400" />
          <span className="text-[11px] font-bold text-slate-400">
            {left === 0
              ? 'Nothing left in their name.'
              : `${left} ${left === 1 ? 'item' : 'items'} still to hand over.`}
          </span>
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="ml-auto text-[11px] font-bold text-indigo-600"
          >
            {open ? 'Hide the list' : 'Show the list'}
          </button>
        </div>
      ) : null}

      {open ? (
        detail.isPending ? (
          <p className="text-xs font-semibold text-slate-400">Loading the handover…</p>
        ) : (detail.data?.items || []).length === 0 ? (
          <p className="text-xs font-semibold text-emerald-600">Handover complete.</p>
        ) : (
          <ul className="space-y-2">
            {(detail.data?.items || []).map((item) => (
              <li
                key={`${item.kind}:${item.itemId}`}
                className="space-y-2 rounded-xl border border-slate-100 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-extrabold text-slate-700">{item.title}</p>
                    <p className="text-[11px] font-semibold text-slate-400">
                      {whenText(item.startsAt)} · {item.status}
                    </p>
                  </div>
                  <Pill tone={item.kind === 'security_shift'
                    ? 'bg-sky-50 text-sky-700'
                    : 'bg-indigo-50 text-indigo-700'}
                  >
                    {item.kind === 'security_shift' ? 'shift' : 'job'}
                  </Pill>
                </div>
                <div className="flex flex-wrap gap-2">
                  {/* No successor named is the ordinary case: the ranking picks
                      whoever is already in this community that day, then whoever
                      is least loaded, then whoever is nearest. The select beside
                      it is the override for when a manager knows better. */}
                  <button
                    type="button"
                    disabled={reassign.isPending}
                    onClick={() => reassign.mutate({ kind: item.kind, itemId: item.itemId })}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white disabled:opacity-60"
                  >
                    <Shuffle className="h-3.5 w-3.5" />Hand over
                  </button>
                  <select
                    className={`${inputClass} max-w-[14rem]`}
                    defaultValue=""
                    disabled={reassign.isPending}
                    onChange={(event) => {
                      if (!event.target.value) return;
                      reassign.mutate({
                        kind: item.kind,
                        itemId: item.itemId,
                        staffAssignmentId: event.target.value,
                      });
                      event.target.value = '';
                    }}
                  >
                    <option value="">…or pick someone</option>
                    {successors.map((member) => (
                      <option key={member.id} value={member.id}>{member.name}</option>
                    ))}
                  </select>
                </div>
              </li>
            ))}
          </ul>
        )
      ) : null}

      {reassign.error ? (
        <p role="alert" className="text-xs font-semibold text-rose-600">
          {reassign.error.message}
        </p>
      ) : null}

      {isPending ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            {/* Approves at the *requested* date. Setting a different date, and
                the coverage check, live on the employee page. */}
            <button
              type="button"
              disabled={decide.isPending}
              onClick={() => decide.mutate({ decision: 'approve' })}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-emerald-600 py-2.5 text-xs font-bold text-white disabled:opacity-50"
            >
              <Check className="h-4 w-4" />Approve
            </button>
            <button
              type="button"
              disabled={decide.isPending}
              onClick={() => {
                const note = window.prompt('Why is this being refused? (optional)');
                if (note === null) return;
                decide.mutate({ decision: 'reject', note: note.trim() || null });
              }}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-60"
            >
              <X className="h-4 w-4" />Reject
            </button>
          </div>
          {(departure.conflictCount ?? left) > 0 ? (
            <p className="text-[11px] font-semibold text-slate-400">
              Approving releases {departure.conflictCount ?? left} booked{' '}
              {(departure.conflictCount ?? left) === 1 ? 'item' : 'items'} back to the
              pool for reassignment.
            </p>
          ) : null}
        </>
      ) : null}

      {decide.error ? (
        <p role="alert" className="text-xs font-semibold text-rose-600">{decide.error.message}</p>
      ) : null}
    </article>
  );
}

export default function DepartmentHiring() {
  const { departmentId } = useParams();
  const queryClient = useQueryClient();
  // The tab lives in the URL, not in useState: the backend has emitted
  // `?tab=applications` / `?tab=departures` notification links since 0043,
  // and a deep link that lands on the default tab is a link that lies.
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const tab = TABS.some((entry) => entry.id === tabParam) ? tabParam : 'applications';
  const setTab = (next) => {
    setSearchParams((params) => {
      const copy = new URLSearchParams(params);
      copy.set('tab', next);
      return copy;
    }, { replace: true });
  };
  const [search, setSearch] = useState('');

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['hiring', departmentId] });
  };

  const applications = useQuery({
    queryKey: ['hiring', departmentId, 'applications'],
    queryFn: () => hiringApi.applications(departmentId),
  });
  // The departures tab needs the roster too, for the successor select.
  const department = useQuery({
    queryKey: ['hiring', departmentId, 'roster'],
    queryFn: () => hiringApi.department(departmentId),
    enabled: tab === 'roster' || tab === 'departures',
  });
  const departures = useQuery({
    queryKey: ['hiring', departmentId, 'departures'],
    queryFn: () => hiringApi.departures(departmentId),
    enabled: tab === 'departures',
  });
  const candidates = useQuery({
    queryKey: ['hiring', departmentId, 'candidates', search],
    queryFn: () => hiringApi.candidates(departmentId, { q: search || undefined }),
    enabled: tab === 'candidates',
  });

  const decide = useMutation({
    mutationFn: ({ applicationId, payload }) =>
      hiringApi.decide(departmentId, applicationId, payload),
    onSuccess: invalidate,
  });
  const removeMember = useMutation({
    mutationFn: ({ staffId, reason }) => hiringApi.removeMember(departmentId, staffId, reason),
    onSuccess: invalidate,
  });
  const blacklist = useMutation({
    mutationFn: (payload) => hiringApi.blacklist(departmentId, payload),
    onSuccess: invalidate,
  });
  const startHandover = useMutation({
    mutationFn: ({ staffId, reason }) =>
      hiringApi.openDeparture(departmentId, { staffId, reason }),
    onSuccess: () => { invalidate(); setTab('departures'); },
  });

  const items = applications.data || [];
  const inbox = items.filter((entry) => entry.status !== 'accepted');
  const roster = department.data?.staff || [];

  return (
    <div className="space-y-6">
      {/* One datalist for every job-title field on the screen. */}
      <datalist id="hb-job-titles">
        {JOB_TITLES.map((title) => <option key={title} value={title} />)}
      </datalist>

      <div>
        <Link
          to={`/admin/departments/${departmentId}`}
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-slate-700"
        >
          <ArrowLeft className="h-4 w-4" />Back to department
        </Link>
        <h1 className="mt-3 text-2xl font-extrabold tracking-tight text-slate-900">Hiring</h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          Service people who work across societies. Live data, not the demo roster.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-xs font-bold ${
              tab === id
                ? 'bg-indigo-600 text-white'
                : 'border border-slate-200 bg-white text-slate-600'
            }`}
          >
            <Icon className="h-4 w-4" />{label}
            {id === 'applications' && inbox.length ? ` (${inbox.length})` : ''}
          </button>
        ))}
        <Link
          to="/admin/messages"
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600"
        >
          <MessageSquare className="h-4 w-4" />Messages
        </Link>
      </div>

      {applications.isLoading ? (
        <p className="text-sm font-semibold text-slate-500">Loading…</p>
      ) : applications.error ? (
        <p role="alert" className="text-sm font-semibold text-rose-600">{applications.error.message}</p>
      ) : tab === 'applications' ? (
        inbox.length === 0 ? (
          <Empty>Nothing waiting on you.</Empty>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {inbox.map((application) => (
              <ApplicationCard
                key={application.id}
                application={application}
                pending={decide.isPending}
                onDecide={(applicationId, payload) => decide.mutate({ applicationId, payload })}
              />
            ))}
          </div>
        )
      ) : tab === 'candidates' ? (
        <div className="space-y-4">
          <input
            className={`${inputClass} max-w-md`}
            value={search}
            placeholder="Search by name or trade"
            onChange={(event) => setSearch(event.target.value)}
          />
          {candidates.isLoading ? (
            <p className="text-sm font-semibold text-slate-500">Searching…</p>
          ) : candidates.error ? (
            <p role="alert" className="text-sm font-semibold text-rose-600">{candidates.error.message}</p>
          ) : (candidates.data || []).length === 0 ? (
            <Empty>
              Nobody registered nearby holds a trade this department&apos;s categories need.
            </Empty>
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {(candidates.data || []).map((candidate) => (
                <CandidateCard
                  key={candidate.id}
                  candidate={candidate}
                  departmentId={departmentId}
                  onInvited={invalidate}
                />
              ))}
            </div>
          )}
        </div>
      ) : tab === 'departures' ? (
        departures.isPending ? (
          <p className="text-sm font-semibold text-slate-500">Loading departures…</p>
        ) : departures.error ? (
          <p role="alert" className="text-sm font-semibold text-rose-600">
            {departures.error.message}
          </p>
        ) : (departures.data || []).length === 0 ? (
          <Empty>Nobody is leaving.</Empty>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {(departures.data || []).map((departure) => (
              <DepartureCard
                key={departure.id}
                departure={departure}
                departmentId={departmentId}
                roster={roster}
                onChanged={invalidate}
              />
            ))}
          </div>
        )
      ) : department.isLoading ? (
        <p className="text-sm font-semibold text-slate-500">Loading the roster…</p>
      ) : roster.length === 0 ? (
        <Empty>Nobody on this roster yet.</Empty>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {roster.map((member) => (
            <article
              key={member.id}
              className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  {/* The tile is the doorway to the employee page: schedule,
                      details, and the departure decision when one is open. */}
                  <Link
                    to={`/admin/departments/${departmentId}/staff/${member.id}`}
                    className="font-extrabold text-slate-800 hover:text-indigo-700"
                  >
                    {member.name}
                  </Link>
                  <p className="text-xs font-semibold text-slate-400">
                    {rankLabel(member.rank)}
                    {member.role ? ` · ${member.role}` : ''}
                    {member.shift ? ` · ${member.shift}` : ''}
                  </p>
                </div>
                {/* A roster holds two kinds of row and only one of them is a
                    person with an account. Saying so is what makes the missing
                    Blacklist button below read as a fact rather than a bug. */}
                {member.serviceProviderId
                  ? <Pill tone="bg-indigo-50 text-indigo-700">service partner</Pill>
                  : <Pill>roster name</Pill>}
              </div>

              <div className="flex flex-wrap items-center gap-3 border-t border-slate-50 pt-3">
                {member.phone ? (
                  <span className="text-[11px] font-bold text-slate-400">{member.phone}</span>
                ) : null}
                <span className="text-[11px] font-bold text-slate-400">
                  {member.activeAssignmentCount} open{' '}
                  {member.activeAssignmentCount === 1 ? 'complaint' : 'complaints'}
                </span>
                {/* A different number from the one beside it: that counts open
                    complaints, this counts jobs and shifts actually booked. A
                    complaint can sit with nobody scheduled, and a job can
                    outlive the complaint that caused it. */}
                {member.openCommitmentCount > 0 ? (
                  <span className="text-[11px] font-bold text-amber-600">
                    {member.openCommitmentCount} booked{' '}
                    {member.openCommitmentCount === 1 ? 'item' : 'items'}
                  </span>
                ) : null}
                {member.departureStatus === 'pending' ? (
                  <Pill tone="bg-amber-50 text-amber-700">leaving</Pill>
                ) : null}
              </div>

              {/* Remove and blacklist are deliberately different verbs on
                  different scopes: removal takes somebody off this roster and
                  leaves them free to apply again; blacklisting bars them from
                  the whole community and demands a reason, because a bar nobody
                  wrote a reason for cannot be reviewed later by whoever has to
                  decide whether to lift it. */}
              {/* Removal is refused by the database while anything is still
                  booked in their name, so the button that would 409 is not
                  offered — a handover is started instead. Somebody already on
                  their way out gets neither: their card is in the Departures
                  tab, and two places to press approve is one too many. */}
              <div className="grid grid-cols-2 gap-2">
                {member.departureStatus === 'pending' ? (
                  <button
                    type="button"
                    onClick={() => setTab('departures')}
                    className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-amber-200 py-2.5 text-xs font-bold text-amber-700"
                  >
                    <DoorOpen className="h-4 w-4" />Open handover
                  </button>
                ) : member.openCommitmentCount > 0 ? (
                  <button
                    type="button"
                    disabled={startHandover.isPending}
                    onClick={() => {
                      const reason = window.prompt('Why are they leaving? (optional)');
                      if (reason === null) return;
                      startHandover.mutate({
                        staffId: member.id,
                        reason: reason.trim() || null,
                      });
                    }}
                    className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-60"
                  >
                    <DoorOpen className="h-4 w-4" />Start handover
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={removeMember.isPending}
                    onClick={() => {
                      const reason = window.prompt('Reason for removing them (optional):');
                      if (reason === null) return;
                      removeMember.mutate({ staffId: member.id, reason: reason.trim() || null });
                    }}
                    className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-60"
                  >
                    <UserMinus className="h-4 w-4" />Remove
                  </button>
                )}
                {member.serviceProviderId ? (
                  <button
                    type="button"
                    disabled={blacklist.isPending}
                    onClick={() => {
                      const reason = window.prompt(
                        'Reason for barring them from the whole community (required):'
                      );
                      if (!reason?.trim()) return;
                      blacklist.mutate({
                        serviceProviderId: member.serviceProviderId,
                        reason: reason.trim(),
                      });
                    }}
                    className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-rose-200 py-2.5 text-xs font-bold text-rose-700 disabled:opacity-60"
                  >
                    <Ban className="h-4 w-4" />Blacklist
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      )}

      {decide.error || removeMember.error || blacklist.error || startHandover.error ? (
        <p role="alert" className="text-sm font-semibold text-rose-600">
          {(decide.error || removeMember.error || blacklist.error || startHandover.error).message}
        </p>
      ) : null}
    </div>
  );
}
