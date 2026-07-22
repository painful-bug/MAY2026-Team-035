import React, { useEffect, useMemo, useState } from 'react';
import { FileText, Plus, Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AmenityCard from '../components/AmenityCard.jsx';
import AmenityFormModal from '../components/AmenityFormModal.jsx';
import {
  AMENITIES_REPORTS_PATH,
  getAmenityDetailPath,
} from '../constants/amenityRoutes.js';
import { useAmenitiesStore } from '../store/useAmenitiesStore.js';

export default function AmenitiesManagementPage() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const amenities = useAmenitiesStore((state) => state.amenities);
  const isLoading = useAmenitiesStore((state) => state.isLoading);
  const error = useAmenitiesStore((state) => state.error);
  const isAdding = useAmenitiesStore((state) => state.isAdding);
  const addError = useAmenitiesStore((state) => state.addError);
  const fetchAmenities = useAmenitiesStore((state) => state.fetchAmenities);
  const addAmenity = useAmenitiesStore((state) => state.addAmenity);
  const clearAddError = useAmenitiesStore((state) => state.clearAddError);
  const toggleAmenityStatus = useAmenitiesStore(
    (state) => state.toggleAmenityStatus
  );

  useEffect(() => {
    fetchAmenities();
  }, [fetchAmenities]);

  const filteredAmenities = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    if (!normalizedSearch) {
      return amenities;
    }

    return amenities.filter((amenity) =>
      [amenity.name, amenity.description, amenity.category, amenity.status].some(
        (value) => value.toLowerCase().includes(normalizedSearch)
      )
    );
  }, [amenities, searchTerm]);

  const handleOpenAddModal = () => {
    clearAddError();
    setIsAddModalOpen(true);
  };

  const handleCloseAddModal = () => {
    clearAddError();
    setIsAddModalOpen(false);
  };

  const handleAddAmenity = async (amenityData) => {
    const createdAmenity = await addAmenity(amenityData);

    if (!createdAmenity) {
      return false;
    }

    setIsAddModalOpen(false);
    return true;
  };

  const handleSelectAmenity = (amenityId) => {
    navigate(getAmenityDetailPath(amenityId));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
            Amenities Management
          </h1>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Manage community facilities, availability, requests, and dues at a glance.
          </p>
        </div>
        <div className="flex flex-wrap gap-3 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => navigate(AMENITIES_REPORTS_PATH)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50 hover:text-indigo-600"
          >
            <FileText className="h-4 w-4" />
            Reports
          </button>
          <button
            type="button"
            onClick={handleOpenAddModal}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-all hover:bg-indigo-700"
          >
            <Plus className="h-4 w-4" />
            Add Amenity
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-sm">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search amenities..."
            aria-label="Search amenities"
            className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-sm font-medium text-slate-700 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none"
          />
        </div>
        <span className="self-start whitespace-nowrap rounded-full border border-slate-100 bg-slate-50 px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-wider text-slate-500 sm:self-auto">
          {filteredAmenities.length} amenities
        </span>
      </div>

      {isLoading && amenities.length === 0 ? (
        <div className="rounded-2xl border border-slate-100 bg-white px-6 py-12 text-center text-xs font-semibold text-slate-400">
          Loading amenities...
        </div>
      ) : error && amenities.length === 0 ? (
        <div className="rounded-2xl border border-rose-100 bg-rose-50 px-6 py-12 text-center">
          <p className="text-xs font-bold text-rose-700">{error}</p>
          <button
            type="button"
            onClick={fetchAmenities}
            className="mt-3 rounded-xl border border-rose-100 bg-white px-4 py-2 text-xs font-bold text-rose-700 transition-colors hover:bg-rose-50"
          >
            Try again
          </button>
        </div>
      ) : filteredAmenities.length === 0 ? (
        <div className="rounded-2xl border border-slate-100 bg-white px-6 py-12 text-center text-xs font-semibold text-slate-400">
          No amenities match your search.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {filteredAmenities.map((amenity) => (
            <AmenityCard
              key={amenity.id}
              amenity={amenity}
              onToggleStatus={toggleAmenityStatus}
              onSelect={handleSelectAmenity}
            />
          ))}
        </div>
      )}

      {isAddModalOpen && (
        <AmenityFormModal
          onClose={handleCloseAddModal}
          onSubmit={handleAddAmenity}
          isSubmitting={isAdding}
          submissionError={addError}
        />
      )}
    </div>
  );
}
