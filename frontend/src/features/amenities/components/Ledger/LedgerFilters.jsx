import React from 'react';
import { Search } from 'lucide-react';
import { LEDGER_FILTERS } from '../../constants/ledgerStatuses.js';

export default function LedgerFilters({
  searchQuery,
  onSearchChange,
  activeFilter,
  onFilterChange,
  counts,
}) {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:p-5 lg:flex-row lg:items-center lg:justify-between">
      <div className="relative w-full lg:max-w-sm">
        <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search resident, flat, or booking ID"
          aria-label="Search amenity ledger"
          className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pr-4 pl-10 text-sm font-medium text-slate-700 placeholder:text-slate-400 transition-all focus:border-indigo-500 focus:bg-white focus:outline-none"
        />
      </div>

      <div className="overflow-x-auto">
        <div className="flex min-w-max gap-1 rounded-xl bg-slate-50 p-1">
          {LEDGER_FILTERS.map((filter) => {
            const isActive = activeFilter === filter.value;

            return (
              <button
                key={filter.value}
                type="button"
                aria-pressed={isActive}
                onClick={() => onFilterChange(filter.value)}
                className={`rounded-lg px-3 py-2 text-[11px] font-bold transition-colors ${
                  isActive
                    ? 'bg-white text-indigo-700 shadow-sm'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {filter.label}
                <span className="ml-1.5 text-[10px] opacity-70">
                  {counts[filter.value] ?? 0}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
