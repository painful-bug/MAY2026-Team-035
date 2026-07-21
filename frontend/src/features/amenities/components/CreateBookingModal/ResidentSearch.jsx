import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Search } from 'lucide-react';
import AmenityFormField, {
  amenityInputClasses,
} from '../AmenityFormField.jsx';

export default function ResidentSearch({
  residents,
  value,
  initialResidentName,
  onChange,
  error,
  isLoading,
}) {
  const containerRef = useRef(null);
  const selectedResident = residents.find((resident) => resident.id === value);
  const [query, setQuery] = useState(
    selectedResident?.name ?? initialResidentName ?? ''
  );
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (value && selectedResident?.name) {
      setQuery(selectedResident.name);
    }
  }, [selectedResident?.name, value]);
  const filteredResidents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    if (!normalizedQuery) {
      return residents;
    }

    return residents.filter((resident) =>
      [resident.name, resident.flat, resident.phone].some((field) =>
        field?.toLowerCase().includes(normalizedQuery)
      )
    );
  }, [query, residents]);

  const handleBlur = (event) => {
    if (!containerRef.current?.contains(event.relatedTarget)) {
      setIsOpen(false);
    }
  };

  const handleQueryChange = (event) => {
    setQuery(event.target.value);
    onChange('');
    setIsOpen(true);
  };

  const handleSelect = (resident) => {
    onChange(resident.id);
    setQuery(resident.name);
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} onBlur={handleBlur}>
      <AmenityFormField label="Resident" required error={error}>
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={query}
            onFocus={() => setIsOpen(true)}
            onChange={handleQueryChange}
            placeholder={isLoading ? 'Loading residents...' : 'Search name, flat, or phone'}
            disabled={isLoading}
            aria-invalid={Boolean(error)}
            className={`${amenityInputClasses} pl-10 ${
              error ? 'border-rose-300 focus:border-rose-500' : ''
            }`}
          />

          {isOpen && !isLoading && (
            <div className="absolute z-30 mt-2 max-h-48 w-full overflow-y-auto rounded-xl border border-slate-100 bg-white p-1.5 shadow-lg shadow-slate-100">
              {filteredResidents.length === 0 ? (
                <p className="px-3 py-4 text-center text-xs font-semibold text-slate-400">
                  No residents found.
                </p>
              ) : (
                filteredResidents.map((resident) => (
                  <button
                    key={resident.id}
                    type="button"
                    onClick={() => handleSelect(resident)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
                  >
                    <span>
                      <span className="block text-xs font-bold text-slate-700">
                        {resident.name}
                      </span>
                      <span className="mt-0.5 block text-[10px] font-semibold text-slate-400">
                        {resident.phone}
                      </span>
                    </span>
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600">
                      {resident.flat}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </AmenityFormField>
    </div>
  );
}
