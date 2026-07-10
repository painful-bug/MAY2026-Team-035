import React from 'react';
import {
  BadgeIndianRupee,
  BellRing,
  CalendarCheck2,
  CarFront,
  MessagesSquare,
  PackageOpen,
  ShieldCheck,
  UserCog,
  Users,
  UserRoundCheck,
} from 'lucide-react';
import ToggleSwitch from './ToggleSwitch';

const MODULE_ICONS = Object.freeze({
  residents: Users,
  visitors: UserRoundCheck,
  complaints: MessagesSquare,
  billing: BadgeIndianRupee,
  notices: BellRing,
  amenities: CalendarCheck2,
  security: ShieldCheck,
  parking: CarFront,
  staff: UserCog,
  marketplace: PackageOpen,
});

export default function FeatureModuleCard({ module, enabled, onToggle }) {
  const Icon = MODULE_ICONS[module.icon] ?? PackageOpen;

  return (
    <button
      type="button"
      onClick={() => onToggle(module.id)}
      aria-pressed={enabled}
      className={`group flex min-h-44 w-full flex-col rounded-2xl border p-5 text-left transition-all duration-200 ${
        enabled
          ? 'border-indigo-200 bg-white shadow-md shadow-indigo-50 hover:-translate-y-0.5 hover:border-indigo-300'
          : 'border-slate-100 bg-slate-50/70 hover:border-slate-200 hover:bg-white'
      }`}
    >
      <div className="flex w-full items-start justify-between gap-4">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors duration-200 ${
            enabled
              ? 'bg-indigo-50 text-indigo-600'
              : 'bg-slate-100 text-slate-400 group-hover:text-slate-500'
          }`}
        >
          <Icon className="h-5 w-5" />
        </div>
        <ToggleSwitch enabled={enabled} />
      </div>

      <div className="mt-5 space-y-2">
        <h2
          className={`text-sm font-extrabold transition-colors ${
            enabled ? 'text-slate-900' : 'text-slate-500'
          }`}
        >
          {module.name}
        </h2>
        <p
          className={`text-xs font-medium leading-relaxed transition-colors ${
            enabled ? 'text-slate-500' : 'text-slate-400'
          }`}
        >
          {module.description}
        </p>
      </div>
    </button>
  );
}
