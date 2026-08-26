import { useQuery } from '@tanstack/react-query';
import { QUERY_POLICIES } from '../../lib/api/queryClient';

import SupervisorDashboard from './SupervisorDashboard';
import WorkerHome from './Dashboard';
import { supervisedEngagement } from '../../lib/staffVocabulary';
import { workerApi } from '../../features/worker/workerApi';

// Which landing page `/worker` is, and nothing else.
//
// The worker portal has always had one index: `WorkerHome`, which is a
// technician's day — offers waiting on you, what is booked today, a link to
// your calendar. A supervisor holds none of those. They land here because rank
// is not role (`0035`): `_portal_for` sends every service person to `/worker`,
// and the supervisor and the technician they dispatch hold the same `worker`
// membership. So the portal's front door was showing half its population an
// empty calendar.
//
// **The fork is here rather than inside `WorkerHome`.** `WorkerHome` is a
// technician's screen and stays exactly that — untouched, same file, same
// behaviour, still what a technician sees. A branch inside it would have made
// one component answer two jobs and made "did the technician page change?" a
// question needing an answer.
//
// **The question is asked of the roster, not the session.** Nothing on
// `sessionContext` carries a rank; `GET /worker/snapshot`'s `communities[]` is
// the only place the browser can learn one, and `WorkerLayout` has already
// fetched it under this very key — so this costs no request. Same predicate,
// same first-row rule, as `WorkerDashboard/Complaints.jsx` and
// `WorkOrders.jsx`: `supervisedEngagement` in `lib/staffVocabulary`, stated
// once.
//
// **The known gap, written down rather than half-solved.** Somebody who is a
// supervisor in one society and a technician in another sees the supervisor
// surface here, and their own jobs are then reachable only from the calendar.
// That is the same person the `supervisedEngagement` doc comment already
// describes — one roster row is picked out of several — and the honest fix is
// the portal-wide engagement switcher recorded there, not a second branch in
// this file.

export default function WorkerLanding() {
  const snapshot = useQuery({
    queryKey: ['worker-snapshot'],
    queryFn: workerApi.snapshot,
    ...QUERY_POLICIES.snapshot,
  });

  // In the app this never renders: `WorkerLayout` holds a full-screen
  // "Preparing your workspace…" until the same query settles, and it is the
  // parent of this route. It exists so that neither page is flashed if this
  // component is ever mounted on its own.
  if (snapshot.isPending) {
    return <p className="py-16 text-center text-sm font-semibold text-slate-400">Loading your work…</p>;
  }

  const engagement = supervisedEngagement(snapshot.data?.communities);
  if (!engagement) return <WorkerHome />;

  return <SupervisorDashboard engagement={engagement} />;
}
