import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, MapPin, UserPlus, X } from 'lucide-react';

import { hiringApi } from '../hiringApi';
import { JOB_TITLES } from '../../../lib/staffVocabulary';

// Service people asking to join, answerable without leaving the dashboard.
//
// **This is the notification made actionable.** `apply_to_department` (`0035`)
// already notifies every admin and manager in the community, so the fact
// arrived; what did not was any way to act on it that was not two navigations
// away — and, for a manager, the notification's own link went to `/admin/…`
// and bounced. The panel and the link fix ship together because either alone
// leaves the other half broken.
//
// ONLY INBOUND APPLICATIONS, AND ONLY PENDING ONES.
//
// `GET .../applications` returns both directions and every status: the
// department's own outstanding invitations are in there too. An invitation is
// not ours to accept — only the person we invited can answer it — so a card
// with Accept on it would be offering something the API refuses. Those live on
// the hiring screen, which is a page about the whole negotiation rather than a
// queue of things waiting on you.
//
// ACCEPTING NAMES A JOB TITLE, AND NOTHING ELSE.
//
// The rank is not a choice: everybody hired through this path joins as a team
// member. There is no shift to pick either. So "accept" is one short form
// rather than a trip to another screen — which is what makes it belong on a
// dashboard at all.

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs ' +
  'font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

function RequestCard({ request, departmentId, basePath, onChanged }) {
  const [accepting, setAccepting] = useState(false);
  const [jobTitle, setJobTitle] = useState('');
  const [error, setError] = useState('');

  const decide = useMutation({
    mutationFn: (payload) => hiringApi.decide(departmentId, request.id, payload),
    onSuccess: () => { setAccepting(false); setError(''); onChanged(); },
    onError: (err) => setError(err?.message || 'That could not be saved.'),
  });

  return (
    <article className="space-y-3 rounded-xl border border-amber-100 bg-white/80 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          {/* The name opens the full profile — the same destination the
              candidate list and the notification lead to. `?application=` so
              the decide buttons are on that page too, rather than sending
              somebody who wanted to read a bio back here to answer. */}
          <Link
            to={`${basePath}/departments/${departmentId}/candidates/${request.serviceProviderId}?application=${request.id}`}
            className="text-xs font-extrabold text-slate-800 hover:text-indigo-700"
          >
            {request.providerDisplayName || 'Service partner'}
          </Link>
          <p className="truncate text-[10px] font-semibold text-slate-400">
            {request.providerHeadline || 'No headline'}
          </p>
        </div>
        {request.distanceKm !== null && request.distanceKm !== undefined ? (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-slate-400">
            <MapPin className="h-3 w-3" />
            {request.distanceKm < 1
              ? 'under 1 km'
              : `${request.distanceKm.toFixed(1)} km`}
          </span>
        ) : null}
      </div>

      {request.providerSkillNames?.length ? (
        <div className="flex flex-wrap gap-1">
          {request.providerSkillNames.slice(0, 4).map((skill) => (
            <span
              key={skill}
              className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-bold text-sky-700"
            >
              {skill}
            </span>
          ))}
        </div>
      ) : null}

      {request.message ? (
        <p className="rounded-lg bg-slate-50 p-2.5 text-[10px] font-semibold leading-relaxed text-slate-600">
          “{request.message}”
        </p>
      ) : null}

      {accepting ? (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            decide.mutate({
              decision: 'accepted',
              jobTitle: jobTitle.trim() || null,
            });
          }}
        >
          <input
            className={inputClass}
            list="hb-job-titles"
            value={jobTitle}
            placeholder="Job title (optional)"
            onChange={(event) => setJobTitle(event.target.value)}
          />
          <p className="text-[10px] font-semibold text-slate-400">
            They join as a team member of this department.
          </p>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={decide.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-[11px] font-bold text-white disabled:opacity-60"
            >
              <UserPlus className="h-3.5 w-3.5" />
              {decide.isPending ? 'Hiring…' : 'Confirm'}
            </button>
            <button
              type="button"
              onClick={() => setAccepting(false)}
              className="rounded-lg border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-600"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setAccepting(true)}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 py-2 text-[11px] font-bold text-white"
          >
            <Check className="h-3.5 w-3.5" />Accept
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
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-slate-200 py-2 text-[11px] font-bold text-slate-600 disabled:opacity-60"
          >
            <X className="h-3.5 w-3.5" />Reject
          </button>
        </div>
      )}

      {error ? (
        <p role="alert" className="text-[10px] font-semibold text-rose-600">{error}</p>
      ) : null}
    </article>
  );
}

export default function JoinRequests({ departmentId, basePath }) {
  const queryClient = useQueryClient();

  const applications = useQuery({
    queryKey: ['hiring', departmentId, 'applications'],
    queryFn: () => hiringApi.applications(departmentId, { status: 'pending' }),
    enabled: Boolean(departmentId),
  });

  const requests = Array.isArray(applications.data)
    ? applications.data.filter((entry) => entry.direction === 'applied')
    : [];

  // Nothing waiting is not a state worth a panel. A dashboard that always
  // carries an empty "Join requests" box teaches people to stop looking at it,
  // which is the opposite of what a queue is for.
  if (!departmentId || requests.length === 0) return null;

  return (
    <section className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50 p-5">
      <datalist id="hb-job-titles">
        {JOB_TITLES.map((title) => <option key={title} value={title} />)}
      </datalist>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-extrabold text-amber-900">
            {requests.length === 1
              ? 'Someone wants to join this department'
              : `${requests.length} people want to join this department`}
          </h2>
          <p className="text-[10px] font-semibold text-amber-700">
            Accepting hires them. Rejecting leaves them free to apply again.
          </p>
        </div>
        <Link
          to={`${basePath}/departments/${departmentId}/hiring?tab=applications`}
          className="text-[11px] font-bold text-amber-800 underline"
        >
          Open hiring
        </Link>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {requests.map((request) => (
          <RequestCard
            key={request.id}
            request={request}
            departmentId={departmentId}
            basePath={basePath}
            onChanged={() =>
              queryClient.invalidateQueries({ queryKey: ['hiring', departmentId] })
            }
          />
        ))}
      </div>
    </section>
  );
}
