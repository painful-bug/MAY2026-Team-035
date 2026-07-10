import React from 'react';
import { GripVertical, Trash2 } from 'lucide-react';

export default function CommunityUnitInput({
  unit,
  index,
  unitLabel,
  placeholderPrefix,
  canDelete,
  onChange,
  onDelete,
}) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 transition-all focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-50">
      <GripVertical className="h-4 w-4 shrink-0 text-slate-300" />
      <label htmlFor={`community-unit-${unit.id}`} className="sr-only">
        {unitLabel} {index + 1}
      </label>
      <input
        id={`community-unit-${unit.id}`}
        type="text"
        value={unit.name}
        onChange={(event) => onChange(unit.id, event.target.value)}
        className="min-w-0 flex-1 bg-transparent px-1 py-1.5 text-sm font-semibold text-slate-700 outline-none placeholder:text-slate-400"
        placeholder={`${placeholderPrefix} ${index + 1}`}
      />
      <button
        type="button"
        onClick={() => onDelete(unit.id)}
        disabled={!canDelete}
        aria-label={`Delete ${unit.name || `${unitLabel} ${index + 1}`}`}
        className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-slate-400"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}
