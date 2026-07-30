import { useMemo, useState } from 'react';
import { Building2, Loader2, Search } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCommunitySearch } from '../hooks/useCommunitySearch';
import { registrationApi } from '../registrationApi';

const relationships = [
  ['tenant', 'Tenant'],
  ['owner', 'Owner'],
  ['family_member', 'Family member'],
  ['caregiver', 'Caregiver'],
  ['other', 'Other'],
];

export default function JoinCommunityTab() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);
  const [relationship, setRelationship] = useState('tenant');
  const [phone, setPhone] = useState('');
  const search = useCommunitySearch(query);
  const mine = useQuery({ queryKey: ['my-access-requests'], queryFn: registrationApi.myAccessRequests });
  const pending = useMemo(
    () => mine.data?.items?.find((item) => item.status === 'pending'),
    [mine.data]
  );
  const request = useMutation({
    mutationFn: registrationApi.createAccessRequest,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['my-access-requests'] }),
  });

  const submit = (event) => {
    event.preventDefault();
    if (!selected) return;
    request.mutate({
      community_id: selected.id,
      requested_relationship: relationship,
      phone: phone.trim() || null,
    });
  };

  if (pending) {
    return (
      <div className="rounded-2xl border border-amber-100 bg-amber-50 p-6 text-sm text-amber-900">
        <p className="font-extrabold">Your request is pending</p>
        <p className="mt-1 font-medium">{pending.community.name} will review your request. You can safely return later; this status is stored in HomeBandhu.</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="space-y-2">
        <label htmlFor="community-search" className="text-xs font-bold uppercase tracking-wider text-slate-500">Find your community</label>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input id="community-search" value={query} onChange={(event) => { setQuery(event.target.value); setSelected(null); }} placeholder="Start typing a community name" className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-sm font-medium outline-none focus:border-indigo-500" />
        </div>
        {query.trim().length > 0 && query.trim().length < 2 ? <p className="text-xs font-medium text-slate-500">Enter at least two characters.</p> : null}
        {search.isFetching ? <p className="inline-flex items-center gap-2 text-xs font-medium text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />Searching communities…</p> : null}
        {search.error ? <p role="alert" className="text-xs font-semibold text-rose-600">{search.error.message}</p> : null}
        {search.data?.items?.length ? (
          <ul role="listbox" className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            {search.data.items.map((community) => (
              <li key={community.id}>
                <button type="button" onClick={() => { setSelected(community); setQuery(community.name); }} className={`flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-indigo-50 ${selected?.id === community.id ? 'bg-indigo-50' : ''}`}>
                  <Building2 className="h-4 w-4 text-indigo-600" />
                  <span><span className="block font-bold text-slate-800">{community.name}</span><span className="block text-xs text-slate-500">{community.city || 'Location unavailable'}{community.state ? `, ${community.state}` : ''}</span></span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {query.trim().length >= 2 && !search.isFetching && search.data?.items?.length === 0 ? <p className="text-xs font-medium text-slate-500">No active communities match that name.</p> : null}
      </div>
      {selected ? (
        <div className="grid gap-4 rounded-2xl border border-slate-100 bg-slate-50 p-4 sm:grid-cols-2">
          <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Relationship
            <select value={relationship} onChange={(event) => setRelationship(event.target.value)} className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700">
              {relationships.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Phone (optional)
            <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+919812345678" className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700" />
          </label>
        </div>
      ) : null}
      {request.error ? <p role="alert" className="text-sm font-semibold text-rose-600">{request.error.message}</p> : null}
      <button type="submit" disabled={!selected || request.isPending} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60">
        {request.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        Request to join {selected?.name || 'community'}
      </button>
    </form>
  );
}
