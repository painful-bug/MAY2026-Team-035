import React from 'react';
import { CheckCircle2, MousePointerClick } from 'lucide-react';

export default function InstructionPanel({ title, description, complete = false }) {
  const Icon = complete ? CheckCircle2 : MousePointerClick;

  return (
    <div
      className={`flex items-start gap-3 rounded-2xl border p-4 ${
        complete
          ? 'border-emerald-100 bg-emerald-50/80'
          : 'border-indigo-100 bg-indigo-50/70'
      }`}
    >
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
          complete
            ? 'bg-emerald-100 text-emerald-600'
            : 'bg-indigo-100 text-indigo-600'
        }`}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="space-y-1">
        <p
          className={`text-xs font-extrabold ${
            complete ? 'text-emerald-900' : 'text-indigo-950'
          }`}
        >
          {title}
        </p>
        <p
          className={`text-[11px] font-medium leading-relaxed ${
            complete ? 'text-emerald-700' : 'text-indigo-700'
          }`}
        >
          {description}
        </p>
      </div>
    </div>
  );
}
