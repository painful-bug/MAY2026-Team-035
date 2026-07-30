import { Check, Mail, Phone, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { registrationApi } from '../../features/registration/registrationApi';

export default function PendingRegistrations() {
  const queryClient = useQueryClient();
  const requests = useQuery({
    queryKey: ['admin-access-requests', 'pending'],
    queryFn: () => registrationApi.adminAccessRequests('pending'),
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-access-requests'] });
  const approve = useMutation({ mutationFn: (id) => registrationApi.approveAccessRequest(id), onSuccess: invalidate });
  const reject = useMutation({ mutationFn: ({ id, reason }) => registrationApi.rejectAccessRequest(id, { reason }), onSuccess: invalidate });

  const rejectRequest = (id) => {
    const reason = window.prompt('Reason for rejecting this request:');
    if (reason?.trim()) reject.mutate({ id, reason: reason.trim() });
  };

  if (requests.isLoading) return <p className="text-sm font-semibold text-slate-500">Loading registration requests…</p>;
  if (requests.error) return <p role="alert" className="text-sm font-semibold text-rose-600">{requests.error.message}</p>;
  const items = requests.data?.items || [];

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
          {items.map((request) => (
            <article key={request.id} className="space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
              <div><h2 className="font-extrabold text-slate-800">{request.applicant_name}</h2><p className="text-xs font-semibold text-slate-400">Requested {request.community.name}</p></div>
              <div className="space-y-2 border-y border-slate-50 py-3 text-xs font-semibold text-slate-600">
                <p className="flex items-center gap-2"><Mail className="h-4 w-4 text-slate-400" />{request.applicant_email}</p>
                {request.applicant_phone_e164 ? <p className="flex items-center gap-2"><Phone className="h-4 w-4 text-slate-400" />{request.applicant_phone_e164}</p> : null}
                <p>Relationship: {request.requested_relationship.replace('_', ' ')}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <button type="button" onClick={() => approve.mutate(request.id)} disabled={approve.isPending || reject.isPending} className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-indigo-600 py-2.5 text-xs font-bold text-white disabled:opacity-60"><Check className="h-4 w-4" />Accept</button>
                <button type="button" onClick={() => rejectRequest(request.id)} disabled={approve.isPending || reject.isPending} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 disabled:opacity-60"><X className="h-4 w-4" />Reject</button>
              </div>
            </article>
          ))}
        </div>
      )}
      {approve.error || reject.error ? <p role="alert" className="text-sm font-semibold text-rose-600">{(approve.error || reject.error).message}</p> : null}
    </div>
  );
}
