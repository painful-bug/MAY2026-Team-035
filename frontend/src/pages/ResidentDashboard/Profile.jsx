import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Phone, PhoneCall, Plus, Users } from 'lucide-react';
import { residentApi } from '../../features/resident/residentApi';
import { useAuthStore } from '../../store/authStore';
import { QUERY_POLICIES } from '../../lib/api/queryClient';

// Wired to `docs/API.md` §14 / `backend/app/api/v1/routers/resident_home.py`.
//
// **Shape changes from the demo.**
// - The flat-members table read `users` filtered by `apartmentId` from the
//   admin/tenant roster. `GET /me/household` is narrower and correct: it is
//   scoped to the caller's own flat by the server, carries a `source` field
//   (`member` vs `contact`) the old model never had, and a contact added here
//   grants no account -- unlike `createUsersSlice.addPhoneToApartment`, which
//   used to manufacture a whole user row for a phone number.
// - The five hard-coded "Emergency / Gate", "Administrative" ... contacts are
//   now `GET /directory/contacts`, served from `departments` so the list
//   cannot go stale the way five numbers typed into a component always do.
//
// `currentUser.flat` / `currentUser.tower` are real now: `GET /auth/session`
// returns `membership.unit` (unit_code + building_name) and
// `lib/auth/authService.js` maps it. `tower` is null for standalone homes,
// whose units have no building.
export default function Profile() {
  const currentUser = useAuthStore((s) => s.currentUser);
  const queryClient = useQueryClient();
  const [newPhone, setNewPhone] = useState('');
  const [newName, setNewName] = useState('');

  const householdQuery = useQuery({
    queryKey: ['resident', 'household'],
    queryFn: () => residentApi.household(),
    ...QUERY_POLICIES.detail,
  });
  const contactsQuery = useQuery({
    queryKey: ['resident', 'directory-contacts'],
    queryFn: () => residentApi.directoryContacts(),
    ...QUERY_POLICIES.list,
  });

  const addPhone = useMutation({
    mutationFn: (payload) => residentApi.addHouseholdPhone(payload),
    onSuccess: (household) => {
      queryClient.setQueryData(['resident', 'household'], household);
      setNewPhone('');
      setNewName('');
    },
  });

  const handleAddNumber = (e) => {
    e.preventDefault();
    if (!newPhone.trim()) return;
    addPhone.mutate({ phoneE164: newPhone.trim(), fullName: newName.trim() || '' });
  };

  const household = householdQuery.data || [];
  const contacts = contactsQuery.data || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Resident Profile & Helpdesk</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Review your flat occupancy information and get society contact numbers.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Profile Card */}
        <div className="lg:col-span-5 bg-white border border-slate-100 rounded-2xl shadow-sm p-6 space-y-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-indigo-650 text-white font-extrabold text-2xl flex items-center justify-center shadow-lg shadow-indigo-150">
              {currentUser?.name?.charAt(0)}
            </div>
            <div>
              <h3 className="text-lg font-extrabold text-slate-855">{currentUser?.name}</h3>
              <p className="text-xs font-semibold text-slate-450">{currentUser?.role === 'Admin' ? 'Society Administrator' : currentUser?.role}</p>
              <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-full inline-block mt-1.5 uppercase tracking-wider">
                {currentUser?.status} Account
              </span>
            </div>
          </div>

          <div className="divide-y divide-slate-50 border-t border-b border-slate-50 py-3 space-y-3.5 text-xs font-semibold text-slate-600">
            <div className="flex justify-between items-center py-1.5">
              <span className="text-slate-400 font-bold uppercase text-[9px] tracking-wider">Email Address</span>
              <span className="text-slate-800">{currentUser?.email}</span>
            </div>
            <div className="flex justify-between items-center py-1.5">
              <span className="text-slate-400 font-bold uppercase text-[9px] tracking-wider">Mobile Number</span>
              <span className="text-slate-800">{currentUser?.phone}</span>
            </div>
            <div className="flex justify-between items-center py-1.5">
              <span className="text-slate-400 font-bold uppercase text-[9px] tracking-wider">Flat Number</span>
              <span className="text-slate-800">{currentUser?.flat}</span>
            </div>
            <div className="flex justify-between items-center py-1.5">
              <span className="text-slate-400 font-bold uppercase text-[9px] tracking-wider">Tower Block</span>
              <span className="text-slate-800">{currentUser?.tower ? `Tower ${currentUser.tower}` : '—'}</span>
            </div>
          </div>
        </div>

        {/* Contact Helpdesk Card */}
        <div className="lg:col-span-7 bg-white border border-slate-100 rounded-2xl shadow-sm p-6 space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-50">
            <PhoneCall className="w-5 h-5 text-indigo-650" />
            <h3 className="font-extrabold text-slate-805 text-sm">Management & Emergency Contacts</h3>
          </div>

          {contactsQuery.isLoading ? (
            <p className="py-6 text-center text-xs font-semibold text-slate-400">Loading contacts…</p>
          ) : contactsQuery.error ? (
            <p role="alert" className="py-6 text-center text-xs font-semibold text-rose-600">
              {contactsQuery.error.message || 'Could not load the contact directory.'}
            </p>
          ) : contacts.length === 0 ? (
            <p className="py-6 text-center text-xs font-semibold text-slate-400">
              No departments have published a contact number yet.
            </p>
          ) : (
            <div className="divide-y divide-slate-50">
              {contacts.map((c) => (
                <div key={c.id} className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-bold text-slate-800">{c.name}</p>
                    <p className="text-[10px] text-slate-400 font-semibold mt-0.5">
                      {c.category}
                      {c.opensAt && c.closesAt ? ` · ${c.opensAt}–${c.closesAt}` : ''}
                    </p>
                  </div>

                  {c.phoneE164 ? (
                    <a
                      href={`tel:${c.phoneE164}`}
                      className="px-3.5 py-1.5 bg-slate-50 border border-slate-200 hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-200 text-slate-700 text-xs font-bold rounded-xl transition-all flex items-center gap-1.5"
                    >
                      <Phone className="w-3.5 h-3.5" />
                      {c.phoneE164}
                    </a>
                  ) : (
                    <span className="text-[10px] font-semibold text-slate-400">No number on file</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Flat members — add another number without needing the admin */}
      <div className="bg-white border border-slate-100 rounded-2xl shadow-sm p-6 space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-slate-50">
          <Users className="w-5 h-5 text-indigo-650" />
          <h3 className="font-extrabold text-slate-805 text-sm">Numbers Registered to Your Flat</h3>
        </div>

        {householdQuery.isLoading ? (
          <p className="py-4 text-center text-xs font-semibold text-slate-400">Loading household…</p>
        ) : householdQuery.error ? (
          <p role="alert" className="py-4 text-center text-xs font-semibold text-rose-600">
            {householdQuery.error.message || 'Could not load the household list.'}
          </p>
        ) : household.length === 0 ? (
          <p className="py-4 text-center text-xs font-semibold text-slate-400">
            Nobody is registered to your flat yet.
          </p>
        ) : (
          <div className="divide-y divide-slate-50">
            {household.map((m) => (
              <div key={m.id} className="py-2.5 first:pt-0 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-bold text-slate-800">
                    {m.fullName || (m.source === 'contact' ? 'Unnamed contact' : 'Unnamed member')}
                  </p>
                  <p className="text-[11px] text-slate-500 font-semibold">
                    {m.phoneE164 || 'No number'}
                    {m.relationship ? ` · ${m.relationship}` : ''}
                  </p>
                </div>
                <span
                  className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider border ${
                    m.status === 'Active'
                      ? 'text-emerald-700 bg-emerald-50 border-emerald-100'
                      : m.status === 'Contact'
                      ? 'text-slate-500 bg-slate-100 border-slate-200'
                      : 'text-amber-700 bg-amber-50 border-amber-100'
                  }`}
                >
                  {m.status}
                </span>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleAddNumber} className="grid grid-cols-1 sm:grid-cols-12 gap-2 pt-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Name (optional)"
            className="sm:col-span-4 bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
          />
          <input
            value={newPhone}
            onChange={(e) => setNewPhone(e.target.value)}
            placeholder="+91 9XXXX XXXXX"
            className="sm:col-span-5 bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
          />
          <button
            type="submit"
            disabled={addPhone.isPending}
            className="sm:col-span-3 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold py-2.5 rounded-xl transition-all shadow-sm shadow-indigo-100 inline-flex items-center justify-center gap-1.5 disabled:opacity-60"
          >
            <Plus className="w-4 h-4" /> {addPhone.isPending ? 'Adding…' : 'Add Number'}
          </button>
        </form>
        {addPhone.error && (
          <p role="alert" className="text-xs font-semibold text-rose-600">{addPhone.error.message}</p>
        )}
      </div>
    </div>
  );
}
