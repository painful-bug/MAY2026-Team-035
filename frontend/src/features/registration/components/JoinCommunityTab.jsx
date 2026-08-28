import { useMemo, useState } from 'react';
import { Building2, Loader2 } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import CommunitySearch from '../../../components/common/CommunitySearch';
import { useCommunitySearch } from '../hooks/useCommunitySearch';
import { registrationApi } from '../registrationApi';
import { COMMUNITY_TYPES } from '../../../data/onboarding';

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
  const [countryCode, setCountryCode] = useState('+91');
  const [phone, setPhone] = useState('');
  // Residence claim: free text only (privacy invariant — non-members never see
  // the community's unit inventory). Apartment communities split tower + flat;
  // villa communities take a single villa number.
  const [buildingText, setBuildingText] = useState('');
  const [unitText, setUnitText] = useState('');
  const [dismissedRejected, setDismissedRejected] = useState(false);
  const search = useCommunitySearch(query);
  const mine = useQuery({ queryKey: ['my-access-requests'], queryFn: registrationApi.myAccessRequests });
  const pending = useMemo(
    () => mine.data?.items?.find((item) => item.status === 'pending'),
    [mine.data]
  );
  const rejected = useMemo(
    () => mine.data?.items?.find((item) => item.status === 'rejected'),
    [mine.data]
  );
  const request = useMutation({
    mutationFn: registrationApi.createAccessRequest,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['my-access-requests'] }),
  });

  const apartmentMode = selected?.community_type === COMMUNITY_TYPES.APARTMENT;
  const residenceComplete = Boolean(unitText.trim()) && (!apartmentMode || Boolean(buildingText.trim()));

  const selectCommunity = (community) => {
    setSelected(community);
    setQuery(community.name);
    // A different community means a different address scheme — never carry a
    // residence claim across.
    setBuildingText('');
    setUnitText('');
  };

  const submit = (event) => {
    event.preventDefault();
    if (!selected || !residenceComplete) return;
    request.mutate({
      community_id: selected.id,
      requested_relationship: relationship,
      phone: phone.trim() ? `${countryCode.trim()}${phone.trim()}` : null,
      requested_unit_text: unitText.trim(),
      ...(apartmentMode ? { requested_building_text: buildingText.trim() } : {}),
    });
  };

  if (pending) {
    return (
      <div className="rounded-2xl border border-amber-100 bg-amber-50 p-6 text-sm text-amber-900">
        <p className="font-extrabold">Your request is pending</p>
        <p className="mt-1 font-medium">Request to join the community has been sent to the community admin. Kindly wait for his response.</p>
      </div>
    );
  }

  if (rejected && !dismissedRejected) {
    return (
      <div className="rounded-2xl border border-rose-100 bg-rose-50 p-6 text-sm text-rose-900">
        <p className="font-extrabold">Your application was rejected</p>
        <p className="mt-1 font-medium">The admin rejected your application to join {rejected.community.name}.{rejected.rejection_reason ? ` ${rejected.rejection_reason}` : ''}</p>
        <button type="button" onClick={() => setDismissedRejected(true)} className="mt-4 rounded-xl bg-white px-4 py-2 text-xs font-bold text-indigo-600">Back to community search</button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <CommunitySearch
        label="Find your community"
        value={query}
        onChange={(event) => { setQuery(event.target.value); setSelected(null); setBuildingText(''); setUnitText(''); }}
        placeholder="Start typing a community name"
        hint={query.trim().length > 0 && query.trim().length < 2 ? <p className="text-xs font-medium text-slate-500">Enter at least two characters.</p> : null}
        isLoading={search.isFetching}
        error={search.error?.message}
        items={search.data?.items ?? []}
        showEmpty={query.trim().length >= 2 && !search.isFetching && search.data?.items?.length === 0}
        emptyMessage="No active communities match that name."
        resultsRole="listbox"
        resultsClassName="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
        renderResult={(community) => (
          <button key={community.id} type="button" role="option" aria-selected={selected?.id === community.id} onClick={() => selectCommunity(community)} className={`flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-indigo-50 ${selected?.id === community.id ? 'bg-indigo-50' : ''}`}>
            <Building2 className="h-4 w-4 text-indigo-600" />
            <span><span className="block font-bold text-slate-800">{community.name}</span><span className="block text-xs text-slate-500">{community.city || 'Location unavailable'}{community.state ? `, ${community.state}` : ''}</span></span>
          </button>
        )}
      />
      {selected ? (
        <div className="grid gap-4 rounded-2xl border border-slate-100 bg-slate-50 p-4 sm:grid-cols-2">
          <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Relationship
            <select value={relationship} onChange={(event) => setRelationship(event.target.value)} className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700">
              {relationships.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Phone (optional)
            <span className="flex gap-2">
              <input aria-label="Phone country code" value={countryCode} onChange={(event) => setCountryCode(event.target.value)} inputMode="tel" maxLength="4" placeholder="+91" className="block w-20 shrink-0 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700" />
              <input aria-label="Phone number" value={phone} onChange={(event) => setPhone(event.target.value)} inputMode="tel" placeholder="9876543210" className="block min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700" />
            </span>
          </label>
          {apartmentMode ? (
            <>
              <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Tower / Block
                <input value={buildingText} onChange={(event) => setBuildingText(event.target.value)} required placeholder="C" className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700" />
              </label>
              <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Flat Number
                <input value={unitText} onChange={(event) => setUnitText(event.target.value)} required placeholder="505" className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700" />
              </label>
            </>
          ) : (
            <label className="space-y-2 text-xs font-bold uppercase tracking-wider text-slate-500">Villa Number
              <input value={unitText} onChange={(event) => setUnitText(event.target.value)} required placeholder="Villa-17" className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700" />
            </label>
          )}
        </div>
      ) : null}
      {request.error ? <p role="alert" className="text-sm font-semibold text-rose-600">{request.error.message}</p> : null}
      <button type="submit" disabled={!selected || !residenceComplete || request.isPending} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60">
        {request.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        Request to join {selected?.name || 'community'}
      </button>
    </form>
  );
}
