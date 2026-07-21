import React, { useEffect } from 'react';
import { ArrowLeft, SearchX } from 'lucide-react';
import { Link, Outlet, useParams } from 'react-router-dom';
import AmenityHeader from '../components/AmenityHeader.jsx';
import AmenityTabs from '../components/AmenityTabs.jsx';
import { AMENITIES_ADMIN_PATH } from '../constants/amenityRoutes.js';
import { useAmenitiesStore } from '../store/useAmenitiesStore.js';

function DetailLoadingState() {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white px-6 py-12 text-center text-xs font-semibold text-slate-400">
      Loading amenity workspace...
    </div>
  );
}

function AmenityNotFound({ message }) {
  return (
    <div className="flex min-h-72 items-center justify-center rounded-2xl border border-slate-100 bg-white p-6 text-center">
      <div className="max-w-sm space-y-4">
        <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-slate-50 text-slate-400">
          <SearchX className="h-5 w-5" />
        </span>
        <div className="space-y-1">
          <h1 className="text-base font-extrabold text-slate-800">
            Amenity not found
          </h1>
          <p className="text-xs font-medium leading-relaxed text-slate-400">
            {message}
          </p>
        </div>
        <Link
          to={AMENITIES_ADMIN_PATH}
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-100 px-4 py-2.5 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to amenities
        </Link>
      </div>
    </div>
  );
}

export default function AmenityDetailLayout() {
  const { amenityId } = useParams();
  const selectedAmenity = useAmenitiesStore(
    (state) => state.selectedAmenity
  );
  const detailAmenityId = useAmenitiesStore(
    (state) => state.detailAmenityId
  );
  const isDetailLoading = useAmenitiesStore(
    (state) => state.isDetailLoading
  );
  const detailError = useAmenitiesStore((state) => state.detailError);
  const fetchAmenityById = useAmenitiesStore(
    (state) => state.fetchAmenityById
  );

  useEffect(() => {
    fetchAmenityById(amenityId);
  }, [amenityId, fetchAmenityById]);

  if (detailAmenityId !== amenityId || isDetailLoading) {
    return <DetailLoadingState />;
  }

  if (detailError || !selectedAmenity) {
    return (
      <AmenityNotFound
        message={
          detailError ??
          'The requested amenity may have been removed or the link is invalid.'
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <AmenityHeader amenity={selectedAmenity} />
      <AmenityTabs amenityId={amenityId} />
      <div>
        <Outlet context={{ amenity: selectedAmenity }} />
      </div>
    </div>
  );
}
