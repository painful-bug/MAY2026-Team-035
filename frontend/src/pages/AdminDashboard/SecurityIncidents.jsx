import IncidentPanel from '../../features/security/components/IncidentPanel';
import { PageHeading } from '../../features/security/components/Primitives';

// **This page exists because a notification already pointed at it.** `0040`
// notifies every admin and manager in the community when a `high` or `critical`
// incident is filed, and the `url` it has carried since Step 7 is
// `/admin/security/incidents`. Until this file, clicking that notification
// landed on nothing.
//
// An admin membership passes `require_gate_membership` — `_GATE_ROLES` is
// (security, admin, manager) — so the same panel the security manager triages
// with works here unchanged.

export default function AdminSecurityIncidents() {
  return (
    <div className="space-y-6">
      <PageHeading
        title="Security incidents"
        description="Filed at the gate. High and critical severities are what notified you."
      />
      <IncidentPanel mode="triage" />
    </div>
  );
}
