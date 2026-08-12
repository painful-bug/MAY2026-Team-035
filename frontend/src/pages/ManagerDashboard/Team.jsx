import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';

import { departmentsApi } from '../../features/departments/departmentsApi';
import PendingInvitations from '../../features/departments/components/PendingInvitations';
import { Empty, PageHeading, Pill } from '../../features/security/components/Primitives';
import { useManagerDepartment } from './useManagerDepartment';

// The manager's roster, and the one thing they may add to it.
//
// **A manager creates supervisors, not technicians.** The ruling puts them on
// the same footing as an admin for this: `can_manage_department` guards
// `invite_staff_member`, and it is true for the department's own manager — so
// the same endpoint the admin's department form calls works here unchanged.
//
// Technicians are not creatable from any screen. They register themselves and
// are hired through the applications surface, which is the Hiring tab.

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs ' +
  'font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

export default function ManagerTeam() {
  const { departmentId, roster, pendingInvitations } = useManagerDepartment();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: '', email: '', phone: '' });
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ['departments', departmentId] });

  const invite = useMutation({
    mutationFn: (payload) =>
      departmentsApi.inviteStaffMember(departmentId, { ...payload, rank: 'supervisor' }),
    onSuccess: () => {
      setForm({ name: '', email: '', phone: '' });
      setError('');
      setAdding(false);
      refresh();
    },
    onError: (err) =>
      setError(err?.message || 'That supervisor could not be created.'),
  });

  // Withdrawing and correcting both live inside `PendingInvitations` — they are
  // two answers to the same question ("this person has not arrived") and keeping
  // them together is what stops one screen growing an edit the other lacks.

  if (!departmentId) {
    return (
      <p className="rounded-2xl border border-amber-100 bg-amber-50 p-6 text-xs font-semibold text-amber-800">
        No department is assigned to your account yet.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeading
        title="Team"
        description="Who works in this department, and who is still expected."
        action={
          <button
            type="button"
            onClick={() => setAdding((current) => !current)}
            className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-indigo-700"
          >
            <Plus className="h-4 w-4" /> Add supervisor
          </button>
        }
      />

      {adding && (
        <form
          className="space-y-3 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
          onSubmit={(event) => {
            event.preventDefault();
            if (!form.name.trim() || !form.email.trim()) return;
            invite.mutate({
              name: form.name.trim(),
              email: form.email.trim(),
              phone: form.phone.trim() || null,
            });
          }}
        >
          <p className="text-xs font-extrabold text-slate-700">New supervisor</p>
          {/* Nothing is sent. The address is what their Google sign-in is
              matched against, so a typo produces no bounce — only somebody who
              never appears. The pending list below is where that shows up. */}
          <p className="text-[10px] font-semibold leading-relaxed text-slate-400">
            They join the moment they sign in with this email address. No
            invitation is sent, so check the spelling.
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            <input
              required
              value={form.name}
              onChange={(event) => setForm((c) => ({ ...c, name: event.target.value }))}
              placeholder="Full name"
              className={inputClass}
            />
            <input
              required
              type="email"
              value={form.email}
              onChange={(event) => setForm((c) => ({ ...c, email: event.target.value }))}
              placeholder="Email for sign-in"
              className={inputClass}
            />
            <input
              value={form.phone}
              onChange={(event) => setForm((c) => ({ ...c, phone: event.target.value }))}
              placeholder="Phone (optional)"
              className={inputClass}
            />
          </div>
          {error ? (
            <p role="alert" className="text-[10px] font-semibold text-rose-600">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={invite.isPending}
            className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:bg-slate-300"
          >
            {invite.isPending ? 'Creating…' : 'Create supervisor'}
          </button>
        </form>
      )}

      <PendingInvitations
        departmentId={departmentId}
        invitations={pendingInvitations}
      />


      <section className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-extrabold text-slate-800">On the roster</h2>
        {roster.length === 0 ? (
          <div className="mt-4">
            <Empty>
              Nobody has been hired into this department yet. Use the Hiring tab
              to find service people.
            </Empty>
          </div>
        ) : (
          <ul className="mt-4 space-y-2">
            {roster.map((member) => (
              <li
                key={member.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-3.5 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-slate-700">
                    {member.name}
                  </p>
                  <p className="truncate text-[10px] font-semibold text-slate-400">
                    {[member.role, member.shift].filter(Boolean).join(' · ') || '—'}
                  </p>
                </div>
                <Pill
                  className={
                    member.rank === 'manager'
                      ? 'bg-indigo-50 text-indigo-700'
                      : member.rank === 'supervisor'
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-slate-100 text-slate-600'
                  }
                >
                  {member.rank === 'manager'
                    ? 'Manager'
                    : member.rank === 'supervisor'
                      ? 'Supervisor'
                      : 'Team member'}
                </Pill>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
