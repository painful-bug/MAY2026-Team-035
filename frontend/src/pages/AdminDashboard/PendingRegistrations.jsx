import { useEffect, useState } from 'react';
import { Ban, Check, Home, Mail, Phone, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { QUERY_POLICIES } from '../../lib/api/queryClient';
import { registrationApi } from '../../features/registration/registrationApi';
import { normalizeUnitCode } from '../../features/registration/utils/unitCode';
import { COMMUNITY_TYPES } from '../../data/onboarding';

// The applicant's residence claim, as free text (privacy invariant: they never
// saw the unit inventory). Pre-migration rows have neither text field; a few
// may carry a validated requested_unit_id from the invitation-era path, which
// we can only name once the admin-units list is in hand.
function claimedResidence(request, units) {
  const building = (request.requested_building_text || '').trim();
  const unit = (request.requested_unit_text || '').trim();
  if (unit) return building ? `Tower ${building} · Flat ${unit}` : unit;
  if (request.requested_unit_id) {
    const known = units?.find((item) => item.id === request.requested_unit_id);
    return known ? known.unit_code : 'Unit on file';
  }
  return 'Not stated';
}

export default function PendingRegistrations() {
  const queryClient = useQueryClient();
  const requests = useQuery({
    queryKey: ['admin-access-requests', 'pending'],
    queryFn: () => registrationApi.adminAccessRequests('pending'),
    ...QUERY_POLICIES.list,
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-access-requests'] });

  // This list comes from React Query, not from the dashboard snapshot, so the
  // SSE-driven re-snapshot in DashboardDataBootstrap does not reach it on its
  // own -- the sidebar badge would tick up while the page behind it went stale.
  // DashboardDataBootstrap already dispatches this window event after every
  // refresh, so hanging the invalidation off it keeps the two in step without a
  // second EventSource.
  useEffect(() => {
    const onRefresh = () => invalidate();
    window.addEventListener('homebandhu:dashboard-refresh', onRefresh);
    return () => window.removeEventListener('homebandhu:dashboard-refresh', onRefresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // One inline approval panel open at a time: {id, building, unit}. Approval
  // now REQUIRES a resolvable unit (422 approval_requires_unit otherwise), so
  // Accept opens the panel instead of firing the mutation directly.
  const [panel, setPanel] = useState(null);

  const units = useQuery({
    queryKey: ['admin-units'],
    queryFn: registrationApi.adminUnits,
    enabled: Boolean(panel),
  });

  const approve = useMutation({
    mutationFn: ({ id, unit_code, building_code }) =>
      registrationApi.approveAccessRequest(id, { unit_code, building_code }),
    onSuccess: () => { setPanel(null); invalidate(); },
  });
  const reject = useMutation({ mutationFn: ({ id, reason }) => registrationApi.rejectAccessRequest(id, { reason }), onSuccess: invalidate });
  const blacklist = useMutation({ mutationFn: ({ id, reason }) => registrationApi.blacklistAccessRequest(id, { reason }), onSuccess: invalidate });

  const rejectRequest = (id) => {
    const reason = window.prompt('Reason for rejecting this request:');
    if (reason?.trim()) reject.mutate({ id, reason: reason.trim() });
  };
  const blacklistRequest = (id) => {
    const reason = window.prompt('Reason for blacklisting this resident:');
    if (reason?.trim()) blacklist.mutate({ id, reason: reason.trim() });
  };

  const openPanel = (request) => {
    if (panel?.id === request.id) { setPanel(null); return; }
    const invited = request.requested_unit_id
      ? units.data?.items?.find((item) => item.id === request.requested_unit_id)
      : null;
    setPanel({
      id: request.id,
      building: (request.requested_building_text || '').trim(),
      unit: (request.requested_unit_text || invited?.unit_code || '').trim(),
    });
  };

  const confirmApprove = (request) => {
    if (!panel || panel.id !== request.id) return;
    const unitCode = panel.unit.trim();
    if (!unitCode) return;
    approve.mutate({
      id: request.id,
      unit_code: unitCode,
      building_code: panel.building.trim() || null,
    });
  };

  if (requests.isLoading) return <p className="text-sm font-semibold text-slate-500">Loading registration requests…</p>;
  if (requests.error) return <p role="alert" className="text-sm font-semibold text-rose-600">{requests.error.message}</p>;
  const items = requests.data?.items || [];
  const anyBusy = approve.isPending || reject.isPending || blacklist.isPending;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Pending Registrations</h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">Database-backed requests to join your community.</p>
      </div>
      {items.length === 0 ? (
        <div className="rounded-2xl border border-slate-100 bg-white p-12 text-center shadow-sm"><Check className="mx-auto h-6 w-6 text-emerald-600" /><p className="mt-3 text-sm font-bold text-slate-700">All caught up</p></div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {items.map((request) => {
            const apartmentMode = request.community?.community_type === COMMUNITY_TYPES.APARTMENT;
            const isOpen = panel?.id === request.id;
            const candidate = isOpen ? normalizeUnitCode(panel.building, panel.unit) : null;
            const matched = candidate
              ? units.data?.items?.find((item) => item.unit_code?.toLowerCase() === candidate.toLowerCase())
              : null;
            return (
              <article key={request.id} className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
                <div><h2 className="font-extrabold text-slate-800">{request.applicant_name}</h2><p className="text-xs font-semibold text-slate-400">Requested {request.community.name}</p></div>
                <div className="space-y-2 border-y border-slate-50 py-3 text-xs font-semibold text-slate-600">
                  <p className="flex items-center gap-2"><Mail className="h-4 w-4 text-slate-400" />{request.applicant_email}</p>
                  {request.applicant_phone_e164 ? <p className="flex items-center gap-2"><Phone className="h-4 w-4 text-slate-400" />{request.applicant_phone_e164}</p> : null}
                  <p>Relationship: {request.requested_relationship.replace('_', ' ')}</p>
                  <p className="flex items-center gap-2"><Home className="h-4 w-4 text-slate-400" />Claims: {claimedResidence(request, units.data?.items)}</p>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <button type="button" onClick={() => openPanel(request)} disabled={anyBusy} aria-expanded={isOpen} className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-indigo-600 py-2.5 text-xs font-bold text-white disabled:opacity-60"><Check className="h-4 w-4" />Accept</button>
                  <button type="button" onClick={() => rejectRequest(request.id)} disabled={anyBusy} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-60"><X className="h-4 w-4" />Reject</button>
                  <button type="button" onClick={() => blacklistRequest(request.id)} disabled={anyBusy} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-rose-200 py-2.5 text-xs font-bold text-rose-700 disabled:opacity-60"><Ban className="h-4 w-4" />Blacklist</button>
                </div>
                {isOpen ? (
                  <div className="space-y-3 rounded-xl border border-indigo-100 bg-indigo-50/50 p-3">
                    <p className="text-xs font-bold text-slate-700">Confirm the residence before approving</p>
                    {apartmentMode ? (
                      <div className="grid grid-cols-2 gap-2">
                        <label className="space-y-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">Tower / Block
                          <input value={panel.building} onChange={(event) => setPanel({ ...panel, building: event.target.value })} placeholder="C" className="block w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs font-semibold text-slate-700" />
                        </label>
                        <label className="space-y-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">Flat Number
                          <input value={panel.unit} onChange={(event) => setPanel({ ...panel, unit: event.target.value })} placeholder="505" className="block w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs font-semibold text-slate-700" />
                        </label>
                      </div>
                    ) : (
                      <label className="block space-y-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">Villa Number
                        <input value={panel.unit} onChange={(event) => setPanel({ ...panel, unit: event.target.value })} placeholder="Villa-17" className="block w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs font-semibold text-slate-700" />
                      </label>
                    )}
                    {candidate ? (
                      <p className="text-[11px] font-semibold text-slate-600">
                        {units.isLoading
                          ? 'Checking existing units…'
                          : matched
                            ? `Matches existing unit ${matched.unit_code}`
                            : `Will create unit ${candidate}`}
                      </p>
                    ) : (
                      <p className="text-[11px] font-semibold text-amber-700">A unit is required to approve.</p>
                    )}
                    <button type="button" onClick={() => confirmApprove(request)} disabled={!candidate || approve.isPending} className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-emerald-600 py-2.5 text-xs font-bold text-white disabled:opacity-60"><Check className="h-4 w-4" />Confirm approval</button>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      )}
      {approve.error || reject.error || blacklist.error ? <p role="alert" className="text-sm font-semibold text-rose-600">{(approve.error || reject.error || blacklist.error).message}</p> : null}
    </div>
  );
}
