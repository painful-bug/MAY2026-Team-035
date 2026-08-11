import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, BriefcaseBusiness, UserPlus, Users, Wrench } from 'lucide-react';

import JoinRequests from '../../features/hiring/components/JoinRequests';
import { MetricCard, PageHeading } from '../../features/security/components/Primitives';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { useManagerDepartment } from './useManagerDepartment';

// The department manager's landing page.
//
// Every number here comes from the one read the manager is allowed to make.
// `department_overview` already counts complaints, staff and now skills, so
// there is no second request and no client-side arithmetic that could disagree
// with the admin portal's version of the same figures.

export default function ManagerOverview() {
  const { departmentId, department, roster, pendingInvitations, isLoading, error } =
    useManagerDepartment();

  if (!departmentId) {
    return (
      <div className="rounded-2xl border border-amber-100 bg-amber-50 p-6">
        <h1 className="text-lg font-extrabold text-amber-900">
          No department is assigned to you
        </h1>
        <p className="mt-2 text-xs font-semibold leading-relaxed text-amber-800">
          Your account is a manager, but it does not name a department — so there
          is nothing here to show yet. An administrator can set this from the
          department screen in the admin portal.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return <p className="text-sm font-semibold text-slate-500">Loading your department…</p>;
  }

  if (error) {
    return (
      <p role="alert" className="text-sm font-semibold text-rose-700">
        {error.message || 'Your department could not be loaded.'}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeading
        title={department?.name || 'Your department'}
        description={department?.description || 'Skills, team and hiring.'}
      />

      {/* Above the metrics on purpose: it is the only thing on this page
          somebody is waiting on an answer to. It renders nothing when the
          queue is empty rather than sitting there as a permanent empty box. */}
      <JoinRequests
        departmentId={departmentId}
        basePath={AUTH_ROUTES.MANAGER_DASHBOARD}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          icon={BriefcaseBusiness}
          label="Open complaints"
          value={department?.activeComplaintCount ?? 0}
          detail={`${department?.overdueComplaintCount ?? 0} past their SLA`}
          tone={department?.overdueComplaintCount ? 'rose' : 'indigo'}
        />
        <MetricCard
          icon={Users}
          label="On the roster"
          value={roster.length}
          detail="Hired into this department"
          tone="emerald"
        />
        <MetricCard
          icon={Wrench}
          label="Skills claimed"
          value={department?.skills?.length ?? 0}
          detail="What this department can be matched for"
          tone="indigo"
        />
        <MetricCard
          icon={AlertTriangle}
          label="Not yet arrived"
          value={pendingInvitations.length}
          detail="Invited, waiting on first sign-in"
          tone={pendingInvitations.length ? 'amber' : 'slate'}
        />
      </div>

      {/* A department with no skills matches nobody in the hiring search, so
          this is not decoration — it is the reason the Find people tab would
          come back empty. */}
      {(department?.skills?.length ?? 0) === 0 && (
        <div className="rounded-2xl border border-amber-100 bg-amber-50 p-5">
          <p className="text-xs font-extrabold text-amber-900">
            This department claims no skills yet
          </p>
          <p className="mt-1 text-[11px] font-semibold leading-relaxed text-amber-800">
            Hiring searches match people by skill. Until this department claims
            some, the Find people tab has nothing to offer.{' '}
            <Link
              to={`${AUTH_ROUTES.MANAGER_DASHBOARD}/skills`}
              className="font-bold underline"
            >
              Add skills
            </Link>
          </p>
        </div>
      )}

      <section className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-extrabold text-slate-800">Your team</h2>
          <div className="flex items-center gap-3">
            {/* The button the ruling asked for: service people, nearest first.
                It is the same screen the admin portal has always had — the
                endpoints behind it accepted a manager all along. */}
            {departmentId ? (
              <Link
                to={`${AUTH_ROUTES.MANAGER_DASHBOARD}/departments/${departmentId}/hiring?tab=candidates`}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-[11px] font-bold text-white hover:bg-indigo-700"
              >
                <UserPlus className="h-3.5 w-3.5" />Find service people
              </Link>
            ) : null}
            <Link
              to={`${AUTH_ROUTES.MANAGER_DASHBOARD}/team`}
              className="text-[11px] font-bold text-indigo-600 hover:underline"
            >
              Manage
            </Link>
          </div>
        </div>
        {roster.length === 0 ? (
          <p className="mt-4 rounded-xl bg-slate-50 p-4 text-xs font-semibold text-slate-400">
            Nobody has been hired into this department yet. Service people
            nearest the society are listed first.
          </p>
        ) : (
          <ul className="mt-4 space-y-2">
            {roster.slice(0, 6).map((member) => (
              <li
                key={member.id}
                className="flex items-center justify-between rounded-xl border border-slate-100 px-3.5 py-2.5"
              >
                <span className="text-xs font-bold text-slate-700">{member.name}</span>
                <span className="text-[10px] font-semibold text-slate-400">
                  {member.role || member.rank}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
