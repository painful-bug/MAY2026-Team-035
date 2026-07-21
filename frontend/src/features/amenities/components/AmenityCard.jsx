import React from 'react';
import {
  Clock3,
  ImageIcon,
  IndianRupee,
  UserRoundCheck,
  Users,
} from 'lucide-react';
import { BOOKING_MODE } from '../constants/bookingModes.js';
import AmenityStatusToggle from './AmenityStatusToggle.jsx';

const currencyFormatter = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 0,
});

export default function AmenityCard({
  amenity,
  onToggleStatus,
  onSelect,
}) {
  const pendingBadgeClasses =
    amenity.pendingRequests > 0
      ? 'bg-amber-50 text-amber-700 border-amber-100'
      : 'bg-slate-50 text-slate-500 border-slate-100';
  const duesBadgeClasses =
    amenity.outstandingDues > 0
      ? 'bg-rose-50 text-rose-700 border-rose-100'
      : 'bg-emerald-50 text-emerald-700 border-emerald-100';
  const isSelectable = typeof onSelect === 'function';

  const handleToggleStatus = () => {
    onToggleStatus(amenity.id);
  };

  const handleSelect = () => {
    onSelect?.(amenity.id);
  };

  const handleKeyDown = (event) => {
    if (event.target === event.currentTarget && event.key === 'Enter') {
      handleSelect();
    }
  };

  return (
    <article
      role={isSelectable ? 'link' : undefined}
      tabIndex={isSelectable ? 0 : undefined}
      aria-label={
        isSelectable ? `Open ${amenity.name} workspace` : undefined
      }
      onClick={isSelectable ? handleSelect : undefined}
      onKeyDown={isSelectable ? handleKeyDown : undefined}
      className={`overflow-hidden rounded-2xl border border-slate-100 bg-white transition-colors ${
        isSelectable
          ? 'cursor-pointer hover:border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2'
          : ''
      }`}
    >
      <div className="relative h-44 bg-slate-100">
        {amenity.image ? (
          <img
            src={amenity.image}
            alt={`${amenity.name} facility`}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-slate-300">
            <ImageIcon className="h-8 w-8" />
          </div>
        )}
        <span
          className={`absolute left-4 top-4 rounded-full border px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-wider ${
            amenity.isActive
              ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
              : 'border-slate-200 bg-slate-100 text-slate-600'
          }`}
        >
          {amenity.status}
        </span>
      </div>

      <div className="space-y-5 p-5">
        <div className="space-y-1.5">
          <h2 className="text-base font-extrabold text-slate-800">
            {amenity.name}
          </h2>
          <p className="min-h-10 text-xs font-medium leading-relaxed text-slate-400">
            {amenity.description}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 border-y border-slate-100 py-4">
          <div className="flex items-start gap-2">
            <Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Opening hours
              </p>
              <p className="mt-0.5 text-xs font-bold text-slate-700">
                {amenity.openingHours}
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <Users className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Capacity
              </p>
              <p className="mt-0.5 text-xs font-bold text-slate-700">
                {amenity.bookingMode === BOOKING_MODE.EXCLUSIVE
                  ? 'Exclusive use'
                  : `${amenity.capacity} people`}
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-extrabold ${pendingBadgeClasses}`}
          >
            <UserRoundCheck className="h-3.5 w-3.5" />
            {amenity.pendingRequests} pending
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-extrabold ${duesBadgeClasses}`}
          >
            <IndianRupee className="h-3.5 w-3.5" />
            {currencyFormatter.format(amenity.outstandingDues)} dues
          </span>
        </div>

        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-bold text-slate-700">
              Amenity availability
            </p>
            <p className="text-[10px] font-semibold text-slate-400">
              {amenity.isActive ? 'Visible and available' : 'Currently unavailable'}
            </p>
          </div>
          <AmenityStatusToggle
            checked={amenity.isActive}
            onChange={handleToggleStatus}
            ariaLabel={`${amenity.isActive ? 'Deactivate' : 'Activate'} ${amenity.name}`}
          />
        </div>
      </div>
    </article>
  );
}
