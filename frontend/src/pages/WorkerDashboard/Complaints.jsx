import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import DepartmentComplaintList from '../../features/complaints/components/DepartmentComplaintList';
import { PageHeading } from '../../features/security/components/Primitives';
import { supervisedEngagement } from '../../lib/staffVocabulary';
import { workerApi } from '../../features/worker/workerApi';

// The supervisor's complaints.
//
// **Why this is in the worker portal.** A supervisor holds a `worker`
// membership with the `supervisor` rank on their roster row — rank is not role,
// `0035` settled that — so `_portal_for` sends them to `/worker` like every
// other service person. Their extra authority is a rank, and it lives in
// Postgres as `can_supervise_department`.
//
// **Why the gate is the roster and not the session.** Nothing on the session
// carries a rank; adding one would mean changing `auth_service.py`, which
// belongs to somebody else and is only touched with a design document. The
// worker snapshot already carries every roster row the caller is on, rank
// included — so the question "are you a supervisor anywhere" is already
// answered by a read this portal makes on every screen.
//
// The screen is offered for the *first* department where they rank supervisor
// or manager. Somebody supervising two departments in two societies is possible
// and rare, and a portal-wide department switcher is a bigger idea than this
// screen: it would want to move `communities[]` into a shared context that
// every worker page reads. Recorded here rather than half-built.
//
// `supervisedEngagement` was a local function here until the work-order queue
// arrived in this portal (2026-08-21) and asked the same question. It moved to
// `lib/staffVocabulary`, beside `LEADERSHIP_RANKS` — two copies of "which ranks
// supervise" is the exact failure that file was created to end. Same predicate,
// same first-row rule, no behaviour change.

export default function WorkerComplaints() {
  const snapshot = useQuery({
    queryKey: ['worker-snapshot'],
    queryFn: workerApi.snapshot,
  });

  // `?complaint=` is on every `notify_complaint_staff` row, and since
  // 2026-08-21 `portalUrl.js` sends a supervisor's copy of it here rather than
  // bouncing them home. Reaching the right screen and then hunting for the row
  // is the same defect one step later — `docs/potential issues/12` counts it —
  // so this reads the parameter the manager's screen has always read, and hands
  // it to the same component. Product owner's ruling, 2026-08-21: the deep link
  // highlights on the worker and admin screens both.
  const [params] = useSearchParams();
  const highlightId = params.get('complaint');

  const engagement = supervisedEngagement(snapshot.data?.communities);

  if (snapshot.isLoading) {
    return <p className="text-xs font-semibold text-slate-400">Loading…</p>;
  }

  if (!engagement) {
    return (
      <p className="rounded-2xl border border-slate-100 bg-white p-6 text-xs font-semibold text-slate-500">
        Complaints are shown to supervisors. You are on a roster as a technician,
        and your work arrives as jobs on the dashboard instead.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeading
        title="Complaints"
        description={
          engagement.departmentName
            ? `${engagement.departmentName} — ${engagement.communityName ?? 'the community'}`
            : 'Your department'
        }
      />

      {/* `canMove` is false and that is the whole difference between this page
          and the manager's. A supervisor who could move work out of their own
          department could empty it, and the department receiving it would have
          no say either way — so they ask, and their manager answers. The RPC
          refuses it regardless of what this screen offers. */}
      <DepartmentComplaintList
        departmentId={engagement.departmentId}
        canMove={false}
        highlightId={highlightId}
      />
    </div>
  );
}
