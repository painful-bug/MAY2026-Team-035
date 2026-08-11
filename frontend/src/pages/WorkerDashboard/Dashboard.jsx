import { useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { CalendarDays, Inbox, MapPinned, Wrench } from 'lucide-react';
import { workerApi } from '../../features/worker/workerApi';
import { communityColor } from '../../lib/communityColor';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import JobDetailModal from './JobDetailModal';
import RegisterProvider from './RegisterProvider';

const when = new Intl.DateTimeFormat(undefined, {
  weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
});

// One request fills this whole screen. `GET /worker/snapshot` is the worker's
// half of the same pattern `GET /resident/snapshot` set, and its two null cases
// are the two empty states -- so the "you have not registered" and "nobody has
// hired you" screens are answered by the same call that draws the dashboard,
// rather than by a client trying two endpoints and interpreting a 404.

function JobCard({ job, onOpen }) {
  const colour = communityColor(job.communityId);
  return (
    <button
      type="button"
      onClick={() => onOpen(job.workOrderId)}
      className={`w-full rounded-2xl border border-slate-200 border-l-4 bg-white p-4 text-left transition-shadow hover:shadow-md ${colour.bar}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-extrabold text-slate-900">
            {job.complaintTitle || job.skillName || 'Job'}
          </p>
          <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs font-semibold text-slate-500">
            <span className={`h-2 w-2 shrink-0 rounded-full ${colour.dot}`} />
            {job.communityName || 'Community'}
            {job.locationText ? ` · ${job.locationText}` : ''}
          </p>
        </div>
        {job.priority === 'high' && (
          <span className="shrink-0 rounded-full bg-rose-100 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-rose-700">
            urgent
          </span>
        )}
      </div>
      <p className="mt-2 text-xs font-bold tabular-nums text-slate-700">
        {job.scheduledStartAt ? when.format(new Date(job.scheduledStartAt)) : 'No time set yet'}
      </p>
    </button>
  );
}

function Section({ title, count, children }) {
  return (
    <section>
      <h2 className="mb-2 flex items-baseline gap-2 text-xs font-extrabold uppercase tracking-wider text-slate-500">
        {title}
        {count > 0 && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] text-slate-600">{count}</span>}
      </h2>
      {children}
    </section>
  );
}

function Empty({ icon: Icon, title, body, action }) {
  return (
    <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <Icon className="mx-auto h-10 w-10 text-slate-300" />
      <p className="mt-4 text-base font-extrabold text-slate-800">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-sm font-medium text-slate-500">{body}</p>
      {action}
    </div>
  );
}

export default function WorkerDashboardHome() {
  // Which job is open lives in the URL rather than in component state, because
  // it is a routing contract before it is a UI detail: five notifications in
  // `0036` and `0037` deep-link here, and `NotificationBell` navigates to what
  // they say verbatim. They used to say `/worker/jobs/<id>` and `/worker/jobs
  // ?job=<id>`, and the worker portal has no `jobs` route -- so every one of
  // them fell through `App.jsx`'s catch-all onto the landing page. They now say
  // `/worker?job=<id>`; this is the half that reads it.
  //
  // Nothing is looked up locally: `JobDetailModal` fetches
  // `GET /worker/jobs/{id}` itself, so a link resolves for any job the worker
  // holds, not only one already drawn on this screen.
  const [searchParams, setSearchParams] = useSearchParams();
  const openJob = searchParams.get('job');
  const setOpenJob = useCallback(
    (workOrderId) => {
      const next = new URLSearchParams(searchParams);
      if (workOrderId) next.set('job', workOrderId);
      else next.delete('job');
      // `replace` so closing the modal is not a back-button step of its own.
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams]
  );
  const snapshot = useQuery({ queryKey: ['worker-snapshot'], queryFn: workerApi.snapshot });

  if (snapshot.isPending) {
    return <p className="py-16 text-center text-sm font-semibold text-slate-400">Loading your work…</p>;
  }
  if (snapshot.isError) {
    return (
      <p className="rounded-2xl bg-rose-50 px-5 py-4 text-sm font-semibold text-rose-700">
        {snapshot.error?.message || 'Could not load your dashboard.'}
      </p>
    );
  }

  const { provider, communities = [], pendingOffers = [], today = [], nextJob } = snapshot.data ?? {};

  // Empty state one: signed in, never registered as a service person. This is
  // the screen `applicationUser()` returning null used to hide, because a
  // provider with no membership had no `currentUser` and was bounced to login.
  const profileComplete = provider?.latitude != null
    && provider?.longitude != null
    && (provider?.skillIds?.length ?? 0) > 0;
  if (!profileComplete) return <RegisterProvider provider={provider} />;

  // Empty state two: registered, hired nowhere. Plan point 6 -- a join prompt,
  // not an empty calendar.
  if (communities.length === 0) {
    return (
      <Empty
        icon={MapPinned}
        title="You are not on any roster yet"
        body="Find societies whose departments need your trades, and apply. Nearest first."
        action={
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <Link to={`${AUTH_ROUTES.WORKER_DASHBOARD}/communities?tab=find`} className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-indigo-700">Find work</Link>
            <Link to={`${AUTH_ROUTES.WORKER_DASHBOARD}/communities?tab=applications`} className="rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-50">Check applications</Link>
          </div>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-extrabold text-slate-900">
          {provider.displayName?.split(' ')[0] || 'Hello'}, here is your day
        </h1>
        <p className="mt-1 text-sm font-medium text-slate-500">
          {communities.length} {communities.length === 1 ? 'community' : 'communities'} ·{' '}
          {snapshot.data.openJobCount ?? 0} open {snapshot.data.openJobCount === 1 ? 'job' : 'jobs'}
        </p>
      </div>

      {pendingOffers.length > 0 && (
        <Section title="Waiting on you" count={pendingOffers.length}>
          <div className="grid gap-3 sm:grid-cols-2">
            {pendingOffers.map((job) => (
              <JobCard key={job.assignmentId} job={job} onOpen={setOpenJob} />
            ))}
          </div>
        </Section>
      )}

      <Section title="Today" count={today.length}>
        {today.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white px-5 py-8 text-center">
            <p className="text-sm font-bold text-slate-600">Nothing booked today.</p>
            {nextJob && (
              <p className="mt-1 text-xs font-medium text-slate-500">
                Next up: {nextJob.complaintTitle || nextJob.skillName} ·{' '}
                {nextJob.scheduledStartAt ? when.format(new Date(nextJob.scheduledStartAt)) : 'unscheduled'}
              </p>
            )}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {today.map((job) => (
              <JobCard key={job.assignmentId} job={job} onOpen={setOpenJob} />
            ))}
          </div>
        )}
      </Section>

      {pendingOffers.length === 0 && today.length === 0 && !nextJob && (
        <Empty
          icon={Inbox}
          title="No jobs yet"
          body="Offers arrive here as soon as a supervisor schedules one for your trade. Keep your availability up to date so the dispatcher can reach you."
          action={
            <Link
              to={`${AUTH_ROUTES.WORKER_DASHBOARD}/availability`}
              className="mt-5 inline-block rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-50"
            >
              Set your hours
            </Link>
          }
        />
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Link
          to={`${AUTH_ROUTES.WORKER_DASHBOARD}/calendar`}
          className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 hover:shadow-md"
        >
          <CalendarDays className="h-5 w-5 text-indigo-600" />
          <span className="text-sm font-bold text-slate-800">See the whole month</span>
        </Link>
        <Link
          to={`${AUTH_ROUTES.WORKER_DASHBOARD}/communities`}
          className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 hover:shadow-md"
        >
          <Wrench className="h-5 w-5 text-indigo-600" />
          <span className="text-sm font-bold text-slate-800">Where I work</span>
        </Link>
      </div>

      {openJob && <JobDetailModal workOrderId={openJob} onClose={() => setOpenJob(null)} />}
    </div>
  );
}
