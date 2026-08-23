import React from 'react';
import { Navigate, useLocation, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import WorkOrderTriage from '../AdminDashboard/WorkOrderTriage';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { supervisedEngagement } from '../../lib/staffVocabulary';
import { workerApi } from '../../features/worker/workerApi';

// The supervisor's dispatch queue, in the portal the supervisor actually lands
// in.
//
// **Why this file is four lines of logic and no screen.** The screen is
// `AdminDashboard/WorkOrderTriage`, unchanged and unforked, because the eight
// endpoints behind it have admitted a supervisor from the day they shipped:
// `work_orders.py` guards the router on "any staff" and every RPC narrows to
// `can_supervise_department`, which a `supervisor` roster row satisfies. What
// was missing was never a permission — it was a route. "The supervisor is the
// channel through whom the worker gets the job" (product owner, 2026-08-21),
// and until now their entire workspace was one complaint list with one button.
//
// **Why a wrapper at all, when `/manager` mounts the triage screen directly.**
// Two things the manager portal gets from its session and this one cannot:
//
//   * *Rank.* `_portal_for` sends every service person to `/worker` — the
//     supervisor and the technician they dispatch hold the same `worker`
//     membership, because rank is not role (`0035`). Nothing on
//     `sessionContext` carries a rank, so the only place the browser can learn
//     one is `GET /worker/snapshot`'s `communities[]`, which this portal
//     already reads on every screen.
//   * *A department.* `usePortalScope` falls back to `currentUser.departmentId`
//     when the URL has none. That is the membership's department, which is
//     right for a manager; for a supervisor the roster row is the truth, and it
//     is the row that carries `departmentId`.
//
// So this resolves both from the snapshot and then gets out of the way. The
// refusal for a technician is `WorkerDashboard/Complaints.jsx`'s, in the same
// words and for the same reason: their work arrives as jobs, and a queue that
// 403s row by row would tell them that far less clearly.

export default function WorkerWorkOrders() {
  const { departmentId } = useParams();
  const { search } = useLocation();
  const snapshot = useQuery({
    queryKey: ['worker-snapshot'],
    queryFn: workerApi.snapshot,
  });

  const engagement = supervisedEngagement(snapshot.data?.communities);

  if (snapshot.isLoading) {
    return <p className="text-xs font-semibold text-slate-400">Loading…</p>;
  }

  if (!engagement) {
    return (
      <p className="rounded-2xl border border-slate-100 bg-white p-6 text-xs font-semibold text-slate-500">
        Work orders are shown to supervisors. You are on a roster as a
        technician, and your work arrives as jobs on the dashboard instead.
      </p>
    );
  }

  // `/worker/work-orders` is the nav item's URL, because a nav item cannot know
  // a department id before the snapshot has loaded. It lands on the same shape
  // every other portal uses — `{base}/departments/:departmentId/work-orders` —
  // rather than rendering the queue at a second address, so that a link copied
  // out of this screen names the department it was about. The search string
  // rides along: `0037`'s supervisor notifications carry `?job=`.
  if (!departmentId) {
    return (
      <Navigate
        replace
        to={{
          pathname: `${AUTH_ROUTES.WORKER_DASHBOARD}/departments/${engagement.departmentId}/work-orders`,
          search,
        }}
      />
    );
  }

  // The id in the URL is passed through untouched, including when it is not the
  // one above. Typing somebody else's is not a way in — `can_supervise_department`
  // refuses it in Postgres, which is the posture `work_orders.py` states
  // outright: an id arriving in a URL is never an authorization decision. What
  // the rank check above buys is the honest sentence for the person who has no
  // department queue at all, not a second copy of the boundary.
  return <WorkOrderTriage />;
}
