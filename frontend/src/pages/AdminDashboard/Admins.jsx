import React, { useState } from 'react';
// The promote modal renders through a portal to document.body. In place, it
// sat inside AdminLayout's `<main class="animate-fade-in">` — a fill-forwards
// opacity animation keeps <main> a stacking context forever, so `z-[999]` was
// trapped at <main>'s own level and the sticky header's `z-40` painted above
// it. Same fix as the departments modals (Departments.jsx).
import { createPortal } from 'react-dom';
import { useMutation } from '@tanstack/react-query';
import { useApp } from '../../store/useApp';
import { ShieldCheck, Plus, User, Mail, Phone, Users as UsersIcon } from 'lucide-react';
import { peopleApi } from '../../features/people/peopleApi';
import { getDashboardSnapshot } from '../../lib/dashboard/dashboardApi';

export default function Admins() {
  const users = useApp((state) => state.users);
  const hydrateDashboard = useApp((state) => state.hydrateDashboard);
  const showToast = useApp((state) => state.showToast);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [tower, setTower] = useState('A');
  const [flat, setFlat] = useState('');

  const admins = users.filter(u => u.role === 'Admin');

  // `POST /admins` *promotes* an existing member -- it does not invite one.
  // The response is the promoted `AdminSummary`, but the source of truth for
  // this screen's list is the dashboard snapshot (`GET /admins` has no route
  // of its own; the directory is served by `users[]`), so success re-pulls the
  // snapshot rather than splicing the response in locally.
  const promote = useMutation({
    mutationFn: (payload) => peopleApi.promoteAdmin(payload),
    onSuccess: async (admin) => {
      const snapshot = await getDashboardSnapshot();
      hydrateDashboard(snapshot);
      showToast(`${admin.name || admin.email} is now an admin`, 'success');
      setName('');
      setEmail('');
      setPhone('');
      setFlat('');
      setModalOpen(false);
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name || !email || promote.isPending) return;
    // `name`, `phone`, `tower`, `flat` travel with the request but the server
    // ignores all four -- the member already has them on their profile, and a
    // promotion must not silently rewrite where somebody lives.
    promote.mutate({ email: email.trim(), name: name.trim(), phone, tower, flat });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">System Administrators</h1>
          <p className="text-xs font-semibold text-slate-400 mt-1">Manage society council members, committee leaders, and app administrators.</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-all shadow-md shadow-indigo-100 flex items-center gap-1.5"
        >
          <Plus className="w-4 h-4" />
          Add Admin
        </button>
      </div>

      {/* Admins Grid */}
      {admins.length === 0 ? (
        <div className="bg-white border border-slate-100 rounded-2xl p-12 text-center shadow-sm">
          <UsersIcon className="w-6 h-6 text-slate-300 mx-auto" />
          <p className="mt-3 text-sm font-bold text-slate-500">No administrators yet.</p>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Promote an existing member to give them admin access.
          </p>
        </div>
      ) : (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {admins.map((adm) => (
          <div key={adm.id} className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm space-y-4 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-3.5 pb-3 border-b border-slate-50">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-650 flex items-center justify-center font-extrabold">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-slate-855 text-sm">{adm.name}</h3>
                <span className="text-[10px] font-bold text-slate-400">Society Administrator</span>
              </div>
            </div>

            <div className="space-y-2 text-xs font-semibold text-slate-600">
              <div className="flex justify-between">
                <span className="text-slate-400 font-bold uppercase text-[9px] tracking-wider">Email Address</span>
                <span className="text-slate-800">{adm.email}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400 font-bold uppercase text-[9px] tracking-wider">Mobile Number</span>
                <span className="text-slate-800">{adm.phone}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400 font-bold uppercase text-[9px] tracking-wider">Office flat</span>
                <span className="text-slate-800">{adm.flat ? `Flat ${adm.flat} (${adm.tower})` : 'Main Office'}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      )}

      {/* Add Admin Modal */}
      {modalOpen && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Promote to admin"
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4"
        >
          <div className="max-h-[calc(100dvh-2rem)] w-full max-w-md space-y-6 overflow-y-auto rounded-3xl border border-slate-100 bg-white p-6 animate-slide-up">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-extrabold text-slate-900">Promote to Admin</h3>
              <button
                onClick={() => { promote.reset(); setModalOpen(false); }}
                className="text-xs font-bold text-slate-400 hover:text-slate-650"
              >
                Cancel
              </button>
            </div>

            {/* This promotes an existing member; it does not invite one. Only
                the email is used to find them -- name, phone, tower and flat
                below are accepted but ignored, because the member already has
                all four on their own profile and residency. */}
            <p className="text-[11px] font-semibold text-slate-400 -mt-2">
              Promotes an existing member to admin by email. If they haven&apos;t
              joined the community yet, invite them first.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Full Name</label>
                <div className="relative">
                  <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. Aakash Deka"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-750 font-medium"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    required
                    placeholder="e.g. admin.office@homebandhu.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-750 font-medium"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Mobile Number</label>
                <div className="relative">
                  <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="e.g. +91 99999 88888"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-750 font-medium"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Tower Location</label>
                  <select
                    value={tower}
                    onChange={(e) => setTower(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  >
                    <option value="A">Tower A</option>
                    <option value="B">Tower B</option>
                    <option value="C">Tower C</option>
                    <option value="D">Tower D</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Flat Number</label>
                  <input
                    type="text"
                    placeholder="e.g. 502"
                    value={flat}
                    onChange={(e) => setFlat(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-750 font-medium"
                  />
                </div>
              </div>

              {promote.error ? (
                <p role="alert" className="text-xs font-semibold text-rose-600">
                  {promote.error.status === 404
                    ? 'No member in this community uses that email yet. Invite them first, then promote once they have joined.'
                    : promote.error.status === 409
                      ? 'That member is already an administrator.'
                      : promote.error.message}
                </p>
              ) : null}

              <button
                type="submit"
                disabled={promote.isPending}
                className="w-full py-3 bg-indigo-650 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 mt-2 text-xs flex items-center justify-center gap-1.5 disabled:opacity-60"
              >
                <Plus className="w-4 h-4" />
                {promote.isPending ? 'Promoting…' : 'Promote to Admin'}
              </button>
            </form>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
