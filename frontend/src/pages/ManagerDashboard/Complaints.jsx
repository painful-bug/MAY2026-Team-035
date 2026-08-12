import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ClipboardList } from 'lucide-react';

import ChangeRequests from '../../features/complaints/components/ChangeRequests';
import DepartmentComplaintList from '../../features/complaints/components/DepartmentComplaintList';
import { PageHeading } from '../../features/security/components/Primitives';
import { useManagerDepartment } from './useManagerDepartment';

// The manager's complaints.
//
// **This screen is the destination that was missing.** `complaint.raised` has
// always notified managers — `notify_community_staff` means every admin *and*
// every manager — and its link was `/admin/complaints`, which a manager's
// portal has no route for, so `ProtectedRoute` bounced them home. Not a 403: a
// redirect, which reads as a click that did nothing.
//
// `complaint_department_routing` fixed both halves. The notification now goes to the *owning*
// department's manager rather than all of them, and this is where it lands.
// Building one without the other would have left either a manager told about
// complaints they cannot open, or a screen nobody is sent to.
//
// A manager may move a complaint out of their department directly; the
// requests panel above is their supervisors asking them to.

export default function ManagerComplaints() {
  const { departmentId, department } = useManagerDepartment();
  // `?complaint=` is on the notification `complaint_department_routing` sends, so this screen has to
  // read it. A parameter no screen reads is `docs/potential issues/12`, and
  // arriving at a list of forty rows with no idea which one you were told
  // about is the same failure as arriving nowhere.
  const [params] = useSearchParams();
  const highlightId = params.get('complaint');

  if (!departmentId) {
    return (
      <p className="rounded-2xl border border-amber-100 bg-amber-50 p-6 text-xs font-semibold text-amber-800">
        No department is assigned to your account yet, so there are no
        complaints to show. An administrator sets this when they create you.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeading
        title="Complaints"
        description={
          department?.name
            ? `Everything routed to ${department.name}`
            : 'Everything routed to your department'
        }
        // Where a complaint stops being a status and becomes somebody
        // arriving at an hour. Deliberately a link out rather than a panel
        // here: this screen is about *whose* a complaint is, and nothing on
        // the triage screen writes `complaints.status` — the two state
        // machines stay uncoupled until the complaint engine says otherwise.
        action={(
          <Link
            to={`/manager/departments/${departmentId}/work-orders`}
            className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-white px-3.5 py-2 text-[11px] font-bold text-indigo-700"
          >
            <ClipboardList className="h-3.5 w-3.5" />
            Work orders
          </Link>
        )}
      />

      <ChangeRequests departmentId={departmentId} />
      <DepartmentComplaintList
        departmentId={departmentId}
        canMove
        highlightId={highlightId}
      />
    </div>
  );
}
