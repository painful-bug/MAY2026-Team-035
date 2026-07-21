import React from 'react';
import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AMENITIES_ADMIN_PATH } from '../constants/amenityRoutes.js';

export default function AmenityHeader({ amenity }) {
  return (
    <header className="space-y-4">
      <Link
        to={AMENITIES_ADMIN_PATH}
        className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 transition-colors hover:text-indigo-600"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </Link>

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          {amenity.name}
        </h1>
        <span
          className={`rounded-full border px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-wider ${
            amenity.isActive
              ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
              : 'border-slate-200 bg-slate-100 text-slate-600'
          }`}
        >
          {amenity.status}
        </span>
      </div>
    </header>
  );
}
