import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Pencil, X } from 'lucide-react';

import { departmentsApi } from '../departmentsApi';

// Leadership who have been created and have not signed in yet — and the two
// things you can do about them.
//
// **Why this panel exists at all.** Nothing is emailed when a manager or
// supervisor is created. The address is not a delivery address, it is the key
// their Google sign-in is matched against. So a typo produces no bounce, no
// error and no signal of any kind — only a row that waits forever. This list is
// the only place the mistake is ever visible.
//
// **Why it is editable, as of 2026-08-12.** Being visible was not enough. The
// product owner's ruling was to keep the single factor and make the mistake
// correctable: "assume the admin won't make typos, and if he notices, let him
// change the email". Before this, the only recovery was withdraw-and-recreate,
// which threw away who issued the original and when.
//
// **Why it is one component and not two panels.** The admin's department page
// and the manager's Team page both show this list, and both needed the same
// fix. Two implementations would have meant fixing the same bug twice and
// finding out later that one of them had drifted — which is exactly the shape
// of the defect that produced `usePortalScope`.
//
// The department is not editable here. It is what the API authorizes the call
// against, so moving somebody to another department is withdraw-and-reissue
// under the authority of wherever they are going, not a field on this form.

const RANKS = [
  ['manager', 'Manager'],
  ['supervisor', 'Supervisor'],
];

const inputClass =
  'w-full rounded-lg border border-amber-200 bg-white px-2.5 py-1.5 text-[11px] ' +
  'font-semibold text-amber-900 focus:border-amber-500 focus:outline-none';

export default function PendingInvitations({ departmentId, invitations }) {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState({ name: '', email: '', phone: '', rank: 'supervisor' });
  const [error, setError] = useState('');

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ['departments', departmentId] });

  const save = useMutation({
    mutationFn: ({ invitationId, payload }) =>
      departmentsApi.updateStaffInvitation(departmentId, invitationId, payload),
    onSuccess: () => {
      setEditingId(null);
      setError('');
      refresh();
    },
    onError: (err) => setError(err?.message || 'That invitation could not be corrected.'),
  });

  const revoke = useMutation({
    mutationFn: (invitationId) =>
      departmentsApi.revokeStaffInvitation(departmentId, invitationId),
    onSuccess: refresh,
    onError: (err) => setError(err?.message || 'That invitation could not be withdrawn.'),
  });

  if (!invitations?.length) return null;

  const startEditing = (invitation) => {
    setError('');
    setEditingId(invitation.id);
    setDraft({
      name: invitation.name || '',
      email: invitation.email || '',
      phone: invitation.phone || '',
      rank: invitation.rank || 'supervisor',
    });
  };

  return (
    <section className="space-y-2 rounded-2xl border border-amber-100 bg-amber-50 p-4">
      <p className="text-[11px] font-extrabold uppercase tracking-wider text-amber-800">
        Waiting for first sign-in
      </p>

      {invitations.map((invitation) =>
        editingId === invitation.id ? (
          <form
            key={invitation.id}
            className="space-y-2 rounded-xl bg-white/80 p-3"
            onSubmit={(event) => {
              event.preventDefault();
              // Only what actually changed. The API reads an omitted field as
              // "leave alone", so sending the whole draft would be harmless but
              // would also overwrite a value somebody else edited in between.
              const payload = {};
              if (draft.name !== invitation.name) payload.name = draft.name;
              if (draft.email !== invitation.email) payload.email = draft.email;
              if (draft.rank !== invitation.rank) payload.rank = draft.rank;
              if (draft.phone !== (invitation.phone || '')) payload.phone = draft.phone;
              if (Object.keys(payload).length === 0) {
                setEditingId(null);
                return;
              }
              save.mutate({ invitationId: invitation.id, payload });
            }}
          >
            <label className="block">
              <span className="text-[9px] font-bold uppercase tracking-wider text-amber-700">
                Name
              </span>
              <input
                className={inputClass}
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              />
            </label>
            <label className="block">
              <span className="text-[9px] font-bold uppercase tracking-wider text-amber-700">
                Email — the address they will sign in with
              </span>
              <input
                className={inputClass}
                type="email"
                value={draft.email}
                onChange={(event) => setDraft({ ...draft, email: event.target.value })}
              />
            </label>
            <div className="flex gap-2">
              <label className="flex-1">
                <span className="text-[9px] font-bold uppercase tracking-wider text-amber-700">
                  Rank
                </span>
                <select
                  className={inputClass}
                  value={draft.rank}
                  onChange={(event) => setDraft({ ...draft, rank: event.target.value })}
                >
                  {RANKS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex-1">
                <span className="text-[9px] font-bold uppercase tracking-wider text-amber-700">
                  Phone
                </span>
                <input
                  className={inputClass}
                  value={draft.phone}
                  onChange={(event) => setDraft({ ...draft, phone: event.target.value })}
                />
              </label>
            </div>
            <div className="flex items-center gap-2 pt-1">
              <button
                type="submit"
                disabled={save.isPending}
                className="inline-flex items-center gap-1 rounded-lg bg-amber-600 px-3 py-1.5 text-[10px] font-bold text-white disabled:bg-slate-300"
              >
                <Check className="h-3 w-3" />
                {save.isPending ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditingId(null);
                  setError('');
                }}
                className="rounded-lg px-3 py-1.5 text-[10px] font-bold text-amber-700 hover:bg-amber-100"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div
            key={invitation.id}
            className="flex items-center justify-between gap-2 rounded-xl bg-white/70 px-3 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-[11px] font-bold text-amber-900">
                {invitation.name}
                {' · '}
                <span className="font-semibold">
                  {invitation.rank === 'manager' ? 'Manager' : 'Supervisor'}
                </span>
              </p>
              <p className="truncate text-[10px] font-semibold text-amber-700">
                {invitation.email}
              </p>
            </div>
            <div className="flex shrink-0 items-center">
              <button
                type="button"
                onClick={() => startEditing(invitation)}
                className="rounded-lg p-1.5 text-amber-700 hover:bg-amber-100"
                aria-label={`Correct the invitation for ${invitation.name}`}
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => revoke.mutate(invitation.id)}
                className="rounded-lg p-1.5 text-amber-700 hover:bg-amber-100"
                aria-label={`Withdraw the invitation for ${invitation.name}`}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )
      )}

      {error && (
        <p className="text-[10px] font-bold text-rose-600" role="alert">
          {error}
        </p>
      )}

      <p className="text-[9px] font-semibold leading-relaxed text-amber-700">
        They join automatically when they sign in with that address. Nothing was
        sent, so if somebody is still waiting, check the spelling and correct it
        here.
      </p>
    </section>
  );
}
