import React from 'react';
import { CheckCircle2, Circle, LocateFixed } from 'lucide-react';

const LOCATION_STATUS = Object.freeze({
  NOT_CONFIGURED: 'Not Configured',
  SELECTED: 'Selected',
  CONFIGURED: 'Configured',
});

const getLocationStatus = (unitId, selectedUnitId, locations) => {
  if (unitId === selectedUnitId) {
    return LOCATION_STATUS.SELECTED;
  }

  return locations[unitId]
    ? LOCATION_STATUS.CONFIGURED
    : LOCATION_STATUS.NOT_CONFIGURED;
};

export default function LocationList({
  units,
  locations,
  selectedUnitId,
  unnamedLabel,
  onSelect,
}) {
  return (
    <div className="max-h-[430px] space-y-2 overflow-y-auto pr-1">
      {units.map((unit) => {
        const status = getLocationStatus(unit.id, selectedUnitId, locations);
        const selected = status === LOCATION_STATUS.SELECTED;
        const configured = status === LOCATION_STATUS.CONFIGURED;
        const StatusIcon = selected
          ? LocateFixed
          : configured
            ? CheckCircle2
            : Circle;

        return (
          <button
            key={unit.id}
            type="button"
            onClick={() => onSelect(unit.id)}
            className={`w-full rounded-xl border p-3 text-left transition-all ${
              selected
                ? 'border-indigo-300 bg-indigo-50 shadow-sm'
                : 'border-slate-200 bg-white hover:border-indigo-200'
            }`}
          >
            <div className="flex items-center gap-3">
              <StatusIcon
                className={`h-4 w-4 shrink-0 ${
                  selected
                    ? 'text-indigo-600'
                    : configured
                      ? 'text-emerald-500'
                      : 'text-slate-300'
                }`}
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-extrabold text-slate-800">
                  {unit.name || unnamedLabel}
                </p>
                <p
                  className={`mt-0.5 text-[10px] font-bold ${
                    selected
                      ? 'text-indigo-600'
                      : configured
                        ? 'text-emerald-600'
                        : 'text-slate-400'
                  }`}
                >
                  {status}
                </p>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
