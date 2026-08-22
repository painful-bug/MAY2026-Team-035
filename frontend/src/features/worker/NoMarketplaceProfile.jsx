import { Building2 } from 'lucide-react';

// The honest empty state for a worker-portal screen that has nothing to show
// somebody who never registered on the marketplace.
//
// Since 2026-08-21 the portal admits department leadership: a manager or a
// supervisor an administrator created by email (`20260812090200`) holds a
// membership and a roster row and **no** `service_providers` row. Four screens
// here are about that missing row — the profile others search, the settings
// that edit it, the availability the dispatcher reads, and the marketplace
// half of "where I work" — and for leadership all four are empty by design
// rather than by accident.
//
// A sentence rather than a hidden nav item, deliberately. Removing the tab
// would leave somebody wondering where their profile went; this says there
// isn't one, and why that is fine.
export default function NoMarketplaceProfile({ title, body, engagements = [] }) {
  const rosters = (engagements ?? []).filter((row) => row?.status === 'active');

  return (
    <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
      <Building2 className="mx-auto h-9 w-9 text-slate-300" />
      <p className="mt-4 text-base font-extrabold text-slate-800">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-sm font-medium text-slate-500">{body}</p>
      {rosters.length > 0 && (
        <div className="mx-auto mt-5 flex max-w-md flex-wrap justify-center gap-2">
          {rosters.map((row) => (
            <span
              key={row.staffAssignmentId}
              className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-bold text-slate-600"
            >
              {row.departmentName || 'Department'}
              {row.communityName ? ` · ${row.communityName}` : ''}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
