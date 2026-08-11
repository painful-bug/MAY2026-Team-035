import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, LogOut, MapPin } from 'lucide-react';
import CommunitySearch from '../../components/common/CommunitySearch';
import { workerApi } from '../../features/worker/workerApi';
import { communityColor } from '../../lib/communityColor';
import { destinationAfterAuth } from '../../routes/authRoutes';
import { useAuthStore } from '../../store/authStore';
import { recordServiceSignupEvent } from '../../lib/telemetry/serviceSignupTelemetry';

// One screen, three panels. The plan gave this three sidebar entries --
// MyCommunities, FindCommunities, Applications -- and they are three views of
// one question, *where do I work*. Journal §4.21 is why they are tabs: a worker
// holding a phone at a job site should not have to know which of three pages
// their pending application is on.

const TABS = [
  ['rosters', 'Where I work'],
  ['find', 'Find work'],
  ['applications', 'My applications'],
];

const STATUS_STYLE = {
  pending: 'bg-amber-50 text-amber-800 border-amber-200',
  accepted: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  rejected: 'bg-rose-50 text-rose-700 border-rose-200',
  withdrawn: 'bg-slate-50 text-slate-600 border-slate-200',
  expired: 'bg-slate-50 text-slate-600 border-slate-200',
};

// Leaving is not something a service person can do alone — and since Phase 2
// Step 6 it starts in Settings, where the modal asks WHEN (immediately or a
// date), which the doc makes part of the request. This card keeps the status
// and the one action that belongs beside it: changing your mind.
function LeaveControl({ row, onChanged }) {
  const departure = row.departure;

  const cancel = useMutation({
    mutationFn: () => workerApi.cancelDeparture(row.staffAssignmentId),
    onSuccess: onChanged,
  });

  if (departure) {
    const requested = departure.requestedEffectiveAt || departure.effectiveAt;
    const day = requested
      ? new Date(requested).toLocaleDateString(undefined, {
        day: 'numeric', month: 'short', year: 'numeric',
      })
      : null;
    return (
      <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
        <p className="text-[11px] font-bold text-amber-600">
          {departure.status === 'approved'
            ? `Approved — you leave ${day || 'now'}.`
            : day
              ? `Asked to leave ${day}. Waiting on the manager.`
              : 'Asked to leave immediately. Waiting on the manager.'}
        </p>
        {departure.status === 'pending' ? (
          <button
            type="button"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate()}
            className="w-full rounded-xl border border-slate-200 py-2 text-[11px] font-bold text-slate-600 disabled:opacity-60"
          >
            Stay after all
          </button>
        ) : null}
        {cancel.error ? (
          <p role="alert" className="text-[11px] font-semibold text-rose-600">{cancel.error.message}</p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mt-3 border-t border-slate-100 pt-3">
      <Link
        to="/worker/settings"
        className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-rose-200 py-2 text-[11px] font-bold text-rose-700 hover:bg-rose-50"
      >
        <LogOut className="h-3.5 w-3.5" />Ask to leave — in Settings
      </Link>
    </div>
  );
}

function Rosters() {
  const queryClient = useQueryClient();
  const rosters = useQuery({ queryKey: ['worker-communities'], queryFn: workerApi.myCommunities });
  const rows = rosters.data ?? [];

  if (rosters.isPending) return <p className="py-10 text-center text-sm font-semibold text-slate-400">Loading…</p>;
  if (rows.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 px-5 py-10 text-center text-sm font-semibold text-slate-500">
        No society employs you yet. Try <span className="font-extrabold">Find work</span>.
      </p>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {rows.map((row) => {
        const colour = communityColor(row.communityId);
        return (
          <div key={row.staffAssignmentId} className={`rounded-2xl border border-l-4 border-slate-200 bg-white p-4 ${colour.bar}`}>
            <p className="flex items-center gap-2 text-sm font-extrabold text-slate-900">
              <span className={`h-2 w-2 rounded-full ${colour.dot}`} />
              {row.communityName}
            </p>
            <p className="mt-1 text-xs font-semibold text-slate-500">
              {row.departmentName}
              {row.communityCity ? ` · ${row.communityCity}` : ''}
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {[row.rank, row.jobTitle, row.shift].filter(Boolean).map((label) => (
                <span key={label} className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold capitalize text-slate-600">
                  {label}
                </span>
              ))}
              {row.status !== 'active' && (
                <span className="rounded-full bg-slate-200 px-2.5 py-1 text-[10px] font-bold text-slate-700">{row.status}</span>
              )}
            </div>
            {row.status === 'active' ? (
              <LeaveControl
                row={row}
                onChanged={() => queryClient.invalidateQueries({ queryKey: ['worker-communities'] })}
              />
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function Find({ onApplied }) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [term, setTerm] = useState('');
  const results = useQuery({
    queryKey: ['worker-community-search', term],
    queryFn: () => workerApi.searchCommunities({ query: term }),
  });
  const profile = useQuery({ queryKey: ['worker-profile'], queryFn: workerApi.profile });
  const applications = useQuery({ queryKey: ['worker-applications'], queryFn: workerApi.myApplications });
  const openDepartments = new Set(
    (applications.data ?? []).filter((row) => row.status === 'pending').map((row) => row.departmentId),
  );
  const apply = useMutation({
    mutationFn: (departmentId) => workerApi.apply({ departmentId }),
    onSuccess: () => {
      void recordServiceSignupEvent('first_application_submitted');
      void queryClient.invalidateQueries({ queryKey: ['worker-applications'] });
      void queryClient.invalidateQueries({ queryKey: ['worker-community-search'] });
      onApplied();
    },
  });

  const rows = results.data ?? [];

  return (
    <div className="space-y-4">
      <CommunitySearch
        inputId="worker-community-search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onSubmit={() => setTerm(query.trim())}
        placeholder="Search by name, or leave blank for the nearest"
        submitLabel="Search"
        isLoading={results.isPending}
        error={results.isError ? results.error?.message || 'Could not search for communities.' : null}
        items={rows}
        showEmpty={results.isSuccess && rows.length === 0}
        emptyMessage="No communities match your skills, name search, and travel radius right now."
        resultsClassName="grid gap-3 sm:grid-cols-2"
        renderResult={(community) => (
          <div key={community.id} className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-extrabold text-slate-900">{community.name}</p>
                <p className="mt-0.5 flex items-center gap-1 truncate text-xs font-semibold text-slate-500">
                  <MapPin className="h-3.5 w-3.5" />
                  {[community.city, community.state].filter(Boolean).join(', ') || 'Location not set'}
                </p>
              </div>
              {community.distanceKm != null && <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold tabular-nums text-slate-600">{community.distanceKm} km</span>}
            </div>
            {community.matchingSkillNames?.length > 0 && <p className="mt-2 text-[11px] font-semibold text-slate-500">Needs: {community.matchingSkillNames.join(', ')}</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              {(community.departments ?? []).map((department) => (
                <button key={department.id} type="button" disabled={apply.isPending || openDepartments.has(department.id)} onClick={() => apply.mutate(department.id)} className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50">
                  {openDepartments.has(department.id) ? 'Application open' : `Apply · ${department.name}`}
                </button>
              ))}
            </div>
          </div>
        )}
      />

      {apply.isError && (
        <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
          {apply.error?.message || 'Could not send that application.'}
        </p>
      )}
      {apply.isSuccess && (
        <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
          Application sent. You will see the manager's answer under My applications.
        </p>
      )}

      <p className="rounded-xl bg-indigo-50 px-4 py-3 text-xs font-semibold text-indigo-800">
        Showing the nearest matches within your {profile.data?.serviceRadiusKm ?? 15} km travel radius. Communities outside it or without coordinates are not shown.
      </p>

    </div>
  );
}

function Applications() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const refreshSession = useAuthStore((state) => state.refreshSession);
  const applications = useQuery({ queryKey: ['worker-applications'], queryFn: workerApi.myApplications });
  const withdraw = useMutation({
    mutationFn: (id) => workerApi.withdrawApplication(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['worker-applications'] }),
  });
  const decision = useMutation({
    mutationFn: ({ id, value }) => workerApi.decideInvitation(id, value),
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['worker-applications'] });
      if (variables.value === 'accepted') {
        const context = await refreshSession();
        navigate(destinationAfterAuth(context), { replace: true });
      }
    },
  });
  const rows = applications.data ?? [];

  if (applications.isPending) return <p className="py-10 text-center text-sm font-semibold text-slate-400">Loading…</p>;
  if (rows.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 px-5 py-10 text-center text-sm font-semibold text-slate-500">
        Nothing open. Applications you send — and invitations departments send you — both land here.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {withdraw.isError || decision.isError ? (
        <p role="alert" className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
          {withdraw.error?.message || decision.error?.message || 'Could not update that application.'}
        </p>
      ) : null}
      {rows.map((application) => (
        <div key={application.id} className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-extrabold text-slate-900">
                <Building2 className="mr-1.5 inline h-4 w-4 text-slate-400" />
                {application.communityName} · {application.departmentName}
              </p>
              <p className="mt-1 text-xs font-semibold text-slate-500">
                {application.direction === 'invited' ? 'They invited you' : 'You applied'}
                {application.rank ? ` · offered ${application.rank}` : ''}
                {application.shift ? ` · ${application.shift}` : ''}
              </p>
              {application.decisionNote && (
                <p className="mt-1.5 rounded-lg bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600">
                  {application.decisionNote}
                </p>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span
                className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${
                  STATUS_STYLE[application.status] || STATUS_STYLE.withdrawn
                }`}
              >
                {application.status}
              </span>
              {application.status === 'pending' && application.direction === 'applied' && (
                <button
                  type="button"
                  disabled={withdraw.isPending}
                  onClick={() => withdraw.mutate(application.id)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                >
                  Withdraw
                </button>
              )}
              {application.status === 'pending' && application.direction === 'invited' && (
                <>
                  <button type="button" disabled={decision.isPending} onClick={() => decision.mutate({ id: application.id, value: 'accepted' })} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50">Accept</button>
                  <button type="button" disabled={decision.isPending} onClick={() => decision.mutate({ id: application.id, value: 'rejected' })} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 disabled:opacity-50">Decline</button>
                </>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function WorkerCommunities() {
  // URL-driven, because notification links land here: the backend has emitted
  // `/worker/communities?tab=applications` as a fallback url since 0043.
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const tab = TABS.some(([key]) => key === tabParam) ? tabParam : 'rosters';
  const setTab = (next) => {
    setSearchParams((params) => {
      const copy = new URLSearchParams(params);
      copy.set('tab', next);
      return copy;
    }, { replace: true });
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-extrabold text-slate-900">Where I work</h1>

      <div className="flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`shrink-0 rounded-lg px-4 py-2 text-xs font-bold transition-colors ${
              tab === key ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'rosters' && <Rosters />}
      {tab === 'find' && <Find onApplied={() => setTab('applications')} />}
      {tab === 'applications' && <Applications />}
    </div>
  );
}
