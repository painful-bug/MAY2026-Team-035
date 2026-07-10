import React from 'react';
import { MapPin } from 'lucide-react';

export default function MapMarker({ point, label }) {
  const position = { left: `${point.x}%`, top: `${point.y}%` };

  return (
    <span
      style={position}
      className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-full"
      aria-hidden="true"
    >
      <span className="flex flex-col items-center">
        <span className="mb-1 max-w-32 truncate rounded-lg bg-slate-900/90 px-2 py-1 text-[10px] font-bold text-white shadow-lg">
          {label}
        </span>
        <span className="flex h-9 w-9 items-center justify-center rounded-full border-2 border-white bg-indigo-600 text-white shadow-xl">
          <MapPin className="h-4 w-4" />
        </span>
      </span>
    </span>
  );
}
