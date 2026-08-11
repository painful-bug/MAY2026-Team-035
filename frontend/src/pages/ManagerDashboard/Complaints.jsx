import React from 'react';
import { useSearchParams } from 'react-router-dom';

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
// `0050` fixed both halves. The notification now goes to the *owning*
// department's manager rather than all of them, and this is where it lands.
// Building one without the other would have left either a manager told about
// complaints they cannot open, or a screen nobody is sent to.
//
// A manager may move a complaint out of their department directly; the
// requests panel above is their supervisors asking them to.

export default function ManagerComplaints() {
  const { departmentId, department } = useManagerDepartment();
  // `?complaint=` is on the notification `0050` sends, so this screen has to
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
