import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Ban, Check, MapPin, MessageCircle, Phone, UserPlus, X,
} from 'lucide-react';

import { QUERY_POLICIES } from '../../lib/api/queryClient';
import { hiringApi } from '../../features/hiring/hiringApi';
import { usePortalScope } from '../../features/hiring/usePortalScope';
import { JOB_TITLES } from '../../lib/staffVocabulary';

// One service person, before they work here.
//
// **The three ways into the hiring surface all land on this page**, and they
// all had nowhere to land before it: a candidate tile in the Find-people tab, a
// card in the Applications inbox, and the `service_application_received`
// notification. Each of them is about somebody who is *not yet on a roster*, so
// the employee page cannot serve them — `GET /departments/{id}/staff/{staffId}`
// reads a `staff_assignments` row, and being considered for a job does not
// create one.
//
// TWO READS, AND THE SECOND ONE IS OPTIONAL.
//
// `GET /service-providers/{id}` is the person: bio, trades, radius, how many
// societies employ them. It knows nothing about *this* department, because the
// row is the person's own registration and carries no community's business.
//
// The department-shaped facts — how far away they are, which of their trades
// this department needs, whether a negotiation is already open — live on the
// list row that linked here, so this page re-reads the candidate list rather
// than inventing a second endpoint that would answer the same question. When
// somebody arrives from a *notification* there is no list row to match, and
// that is a real state rather than an error: the identity panel renders and the
// department-shaped strip says so.

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs ' +
  'font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

function Pill({ children, tone = 'bg-slate-100 text-slate-600' }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${tone}`}>
      {children}
    </span>
  );
}

function Fact({ label, children }) {
  return (
    <div className="rounded-xl border border-slate-100 p-3.5">
      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-xs font-bold text-slate-700">{children}</p>
    </div>
  );
}

export default function CandidateDetail() {
  const { providerId } = useParams();
  const { base: basePath, departmentId } = usePortalScope();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [offering, setOffering] = useState(false);
  const [jobTitle, setJobTitle] = useState('');
  const [message, setMessage] = useState('');

  // The application this person opened, when they arrived from the inbox or a
  // notification. Both carry `?application=` so that the decide buttons appear
  // on the same page as the profile rather than only back on the list.
  const applicationId = searchParams.get('application');

  const candidate = useQuery({
    queryKey: ['hiring', 'candidate', providerId],
    queryFn: () => hiringApi.candidate(providerId),
    ...QUERY_POLICIES.detail,
  });

  // The department's own view of them. Only for the strip: nothing on this page
  // is hidden when it comes back empty, because "not in the candidate list" is
  // true of anybody already on the roster or already in a negotiation, and
  // those are exactly the people a manager most wants to open.
  const listRow = useQuery({
    queryKey: ['hiring', departmentId, 'candidates', ''],
    queryFn: () => hiringApi.candidates(departmentId),
    ...QUERY_POLICIES.list,
    enabled: Boolean(departmentId),
    select: (rows) => (rows || []).find((row) => row.id === providerId) || null,
  });

  const applications = useQuery({
    queryKey: ['hiring', departmentId, 'applications'],
    queryFn: () => hiringApi.applications(departmentId),
    ...QUERY_POLICIES.list,
    enabled: Boolean(departmentId),
    select: (rows) =>
      (rows || []).find((row) =>
        applicationId ? row.id === applicationId : row.serviceProviderId === providerId
          && row.status === 'pending') || null,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['hiring', departmentId] });
    queryClient.invalidateQueries({ queryKey: ['hiring', 'candidate', providerId] });
  };

  const invite = useMutation({
    mutationFn: () =>
      hiringApi.invite(departmentId, {
        serviceProviderId: providerId,
        jobTitle: jobTitle.trim() || null,
        message: message.trim() || null,
      }),
    onSuccess: () => { setOffering(false); invalidate(); },
  });

  const decide = useMutation({
    mutationFn: (payload) =>
      hiringApi.decide(departmentId, applications.data.id, payload),
    onSuccess: invalidate,
  });

  const talk = useMutation({
    mutationFn: () =>
      hiringApi.openConversation({ departmentId, serviceProviderId: providerId }),
    onSuccess: (conversation) =>
      navigate(`${basePath}/messages?conversation=${conversation.id}`),
  });

  const backTo = `${basePath}/departments/${departmentId}/hiring`;

  if (candidate.isLoading) {
    return <p className="text-sm font-semibold text-slate-500">Loading…</p>;
  }

  if (candidate.error) {
    return (
      <div className="space-y-4">
        <Link
          to={backTo}
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-slate-700"
        >
          <ArrowLeft className="h-4 w-4" />Back to hiring
        </Link>
        <p role="alert" className="text-sm font-semibold text-rose-600">
          {candidate.error.message}
        </p>
      </div>
    );
  }

  const person = candidate.data;
  const row = listRow.data;
  const application = applications.data;
  const pendingApplication =
    application && application.status === 'pending' && application.direction === 'applied';
  const pendingInvitation =
    application && application.status === 'pending' && application.direction === 'invited';

  return (
    <div className="max-w-4xl space-y-6">
      <datalist id="hb-job-titles">
        {JOB_TITLES.map((title) => <option key={title} value={title} />)}
      </datalist>

      <Link
        to={backTo}
        className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" />Back to hiring
      </Link>

      <header className="space-y-3 rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
              {person.displayName}
            </h1>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              {person.headline || 'No headline'}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            {person.status === 'active'
              ? <Pill tone="bg-emerald-50 text-emerald-700">registered</Pill>
              : <Pill tone="bg-rose-50 text-rose-700">{person.status}</Pill>}
            {/* Their own toggle, and it is worth showing beside a hire button:
                it does not stop the hire, it stops the dispatcher offering them
                work afterwards. A manager hiring somebody who is offline should
                know they are about to hire somebody who is offline. */}
            {person.isAvailable
              ? <Pill tone="bg-sky-50 text-sky-700">taking work</Pill>
              : <Pill>not taking work</Pill>}
          </div>
        </div>

        {person.bio ? (
          <p className="whitespace-pre-line rounded-xl bg-slate-50 p-4 text-xs font-semibold leading-relaxed text-slate-600">
            {person.bio}
          </p>
        ) : (
          <p className="text-[11px] font-semibold text-slate-400">
            They have not written anything about themselves.
          </p>
        )}

        <div className="flex flex-wrap items-center gap-3 border-t border-slate-50 pt-3">
          {person.phone ? (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-500">
              <Phone className="h-3.5 w-3.5" />{person.phone}
            </span>
          ) : null}
          {/* Distance comes from the list row and never from the profile: the
              endpoint deliberately withholds coordinates, and `distanceKm` is
              measured from this community's own point, which is the question a
              manager actually has. */}
          {row?.distanceKm !== undefined && row?.distanceKm !== null ? (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-500">
              <MapPin className="h-3.5 w-3.5" />
              {row.distanceKm < 1 ? 'under 1 km away' : `${row.distanceKm.toFixed(1)} km away`}
            </span>
          ) : null}
          {/* This one *is* on the profile, unlike the distance above: a coarse
              place name the person published about themselves is theirs to
              publish, and the 120-character cap is what keeps it from being an
              address. */}
          {person.locationLabel ? (
            <span className="text-[11px] font-bold text-slate-400">{person.locationLabel}</span>
          ) : null}
          <span className="text-[11px] font-bold text-slate-400">
            Registered {new Date(person.registeredAt).toLocaleDateString(undefined, {
              month: 'long', year: 'numeric',
            })}
          </span>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Fact label="Works in">
          {person.communityCount} {person.communityCount === 1 ? 'society' : 'societies'}
        </Fact>
        <Fact label="Travels up to">{person.serviceRadiusKm} km</Fact>
        <Fact label="Trades">{person.skillNames.length}</Fact>
      </div>

      <section className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-extrabold text-slate-800">What they do</h2>
        {/* Matching trades first and marked, because `matchingSkillNames` is
            *why* they were offered and `skillNames` is everything they do.
            Showing only the second leaves a manager wondering why an
            electrician is on a plumbing shortlist. */}
        {row?.matchingSkillNames?.length ? (
          <div className="space-y-1.5">
            <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
              Matches this department
            </p>
            <div className="flex flex-wrap gap-1.5">
              {row.matchingSkillNames.map((skill) => (
                <Pill key={skill} tone="bg-indigo-50 text-indigo-700">{skill}</Pill>
              ))}
            </div>
          </div>
        ) : null}
        <div className="space-y-1.5">
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
            Everything they offer
          </p>
          {person.skillNames.length === 0 ? (
            <p className="text-xs font-semibold text-slate-400">
              They have claimed no trades, so no department&apos;s search will
              ever find them.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {person.skillNames.map((skill) => (
                <Pill key={skill} tone="bg-sky-50 text-sky-700">{skill}</Pill>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-extrabold text-slate-800">
          {pendingApplication
            ? 'They have asked to join'
            : pendingInvitation
              ? 'You have offered them a place'
              : 'Offer them a place'}
        </h2>

        {application?.message ? (
          <p className="rounded-xl bg-slate-50 p-3.5 text-xs font-semibold text-slate-600">
            “{application.message}”
          </p>
        ) : null}

        {/* An invitation is ours to withdraw, not ours to accept — only they
            can answer it — so no accept control appears rather than a disabled
            one. A disabled button invites a manager to wonder what unlocks it. */}
        {pendingInvitation ? (
          <p className="text-[11px] font-semibold text-slate-400">
            Waiting on their answer. They have been notified.
          </p>
        ) : pendingApplication ? (
          <div className="space-y-3">
            <label className="block space-y-1.5">
              <span className="text-[11px] font-bold text-slate-500">
                Job title <span className="font-semibold text-slate-400">(optional)</span>
              </span>
              <input
                className={inputClass}
                list="hb-job-titles"
                value={jobTitle}
                placeholder="Plumber"
                onChange={(event) => setJobTitle(event.target.value)}
              />
            </label>
            {/* Rank is not offered. Everyone hired this way is a team member —
                managers and supervisors are provisioned by email and never
                registered as service providers. */}
            <p className="text-[10px] font-semibold text-slate-400">
              They join as a team member of this department.
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={decide.isPending}
                onClick={() =>
                  decide.mutate({
                    decision: 'accepted',
                    jobTitle: jobTitle.trim() || null,
                  })
                }
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
              >
                <Check className="h-4 w-4" />Accept and hire
              </button>
              <button
                type="button"
                disabled={decide.isPending}
                onClick={() => {
                  const note = window.prompt(
                    'Reason for turning this application down (optional):'
                  );
                  if (note === null) return;
                  decide.mutate({ decision: 'rejected', note: note.trim() || null });
                }}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-60"
              >
                <X className="h-4 w-4" />Reject
              </button>
              {/* The **hiring conversation**, not the direct-message dock.
                  They are different surfaces and only one of them works here:
                  `openChatDock` composes a DM to somebody in your community,
                  and a candidate is by definition not in it — that is what
                  makes them a candidate. `POST /conversations` is idempotent on
                  the (department, provider) pair, so this opens the thread or
                  returns the existing one, then deep-links the Messages screen
                  at it the same way the notification does. */}
              <button
                type="button"
                disabled={talk.isPending}
                onClick={() => talk.mutate()}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-60"
              >
                <MessageCircle className="h-4 w-4" />
                {talk.isPending ? 'Opening…' : 'Message'}
              </button>
            </div>
          </div>
        ) : row?.hasOpenApplication ? (
          <p className="text-[11px] font-semibold text-amber-600">
            A negotiation with this person is already open. It is in the
            Applications tab.
          </p>
        ) : offering ? (
          <form
            className="space-y-3"
            onSubmit={(event) => { event.preventDefault(); invite.mutate(); }}
          >
            <input
              className={inputClass}
              list="hb-job-titles"
              value={jobTitle}
              placeholder="Job title (optional)"
              onChange={(event) => setJobTitle(event.target.value)}
            />
            <textarea
              className={inputClass}
              rows={3}
              value={message}
              placeholder="A note with the offer (optional)"
              onChange={(event) => setMessage(event.target.value)}
            />
            <p className="text-[10px] font-semibold text-slate-400">
              They join as a team member when they accept. Nothing happens until
              they do.
            </p>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={invite.isPending}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
              >
                <UserPlus className="h-4 w-4" />
                {invite.isPending ? 'Sending…' : 'Send the offer'}
              </button>
              <button
                type="button"
                onClick={() => setOffering(false)}
                className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button
            type="button"
            onClick={() => setOffering(true)}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white"
          >
            <UserPlus className="h-4 w-4" />Offer them a place
          </button>
        )}

        {invite.error || decide.error ? (
          <p role="alert" className="text-xs font-semibold text-rose-600">
            {(invite.error || decide.error).message}
          </p>
        ) : null}
      </section>

      {/* Blacklisting is not offered here, and that is deliberate rather than
          forgotten. It bars somebody from the whole community and demands a
          reason; the place to do that is the roster, where you are looking at
          somebody you have actually worked with. Refusing a stranger is
          "Reject", which leaves them free to apply again. */}
      <p className="flex items-center gap-1.5 text-[10px] font-semibold text-slate-400">
        <Ban className="h-3.5 w-3.5" />
        Barring somebody from the whole community is done from the roster, not
        from here.
      </p>
    </div>
  );
}
