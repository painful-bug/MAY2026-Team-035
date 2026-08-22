import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { triageApi } from '../../features/triage/triageApi';
import { Failure, ModalShell } from './triageParts';

// The internal note, written once and never edited.
//
// **Who reads it.** Staff and workers; not the resident (amendment 2, ruling
// A5). The endpoint stamps `internal: true` into the `note_added` payload and
// `resident_complaints_service` drops those events from the resident's
// timeline, so this composer is the private margin of the complaint — where a
// supervisor writes "third call about this tap, the riser is the real problem"
// without opening a conversation about it.
//
// **Append-only, and the UI says so rather than discovering it.** There is no
// edit and no delete on the wire, because a timeline somebody can rewrite is
// not a record. The line under the box is that promise, made before the button
// is pressed rather than after.
//
// One component, two frames: inline inside the eye popup, where the note lands
// on the timeline you are already reading, and wrapped in `ModalShell` for the
// note button on a card, where there is no popup open. The mutation lives here
// rather than on the page because nothing outside needs its pending state —
// unlike take-up or resolve, whose refusals belong on a specific card.

const LIMIT = 2000;

export function NoteComposer({ complaintId, onSaved, autoFocus = false }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');
  const trimmed = note.trim();
  const tooLong = trimmed.length > LIMIT;
  const ready = trimmed.length > 0 && !tooLong;

  const save = useMutation({
    mutationFn: () => triageApi.addNote(complaintId, trimmed),
    onSuccess: () => {
      setNote('');
      // The timeline in the popup behind this is the thing that just changed,
      // and the snapshot is not — but a note is written at the same moment a
      // supervisor is deciding something, so both are re-read rather than the
      // screen guessing which one the next glance lands on.
      void queryClient.invalidateQueries({ queryKey: ['staff-complaint', complaintId] });
      void queryClient.invalidateQueries({ queryKey: ['supervisor-triage'] });
      onSaved?.();
    },
  });

  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready && !save.isPending) save.mutate();
      }}
    >
      <label className="block space-y-1.5">
        <span className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
          Internal note
        </span>
        <textarea
          autoFocus={autoFocus}
          rows={3}
          value={note}
          maxLength={LIMIT + 200}
          onChange={(event) => setNote(event.target.value)}
          placeholder="What the next person on this complaint needs to know"
          className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 focus:border-indigo-400 focus:bg-white focus:outline-none"
        />
      </label>
      <p className="text-[11px] font-semibold text-slate-400">
        Staff and workers see this on the complaint&apos;s timeline. The resident
        does not. It cannot be edited or deleted afterwards.
      </p>
      {tooLong ? (
        <p role="alert" className="text-xs font-semibold text-rose-600">
          That is {trimmed.length} characters; the limit is {LIMIT}.
        </p>
      ) : null}
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={!ready || save.isPending}
          className="rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50"
        >
          {save.isPending ? 'Saving…' : 'Save note'}
        </button>
        <span className="text-[11px] font-semibold tabular-nums text-slate-400">
          {trimmed.length}/{LIMIT}
        </span>
      </div>
      <Failure error={save.error} />
    </form>
  );
}

export function NoteModal({ complaintId, title, onClose }) {
  return (
    <ModalShell title="Add an internal note" subtitle={title} onClose={onClose}>
      <NoteComposer complaintId={complaintId} autoFocus onSaved={onClose} />
    </ModalShell>
  );
}
