import React, { useEffect, useMemo, useState } from 'react';
import { ClipboardCheck } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';
import ApprovalFilters from '../components/Approvals/ApprovalFilters.jsx';
import ApprovalTable from '../components/Approvals/ApprovalTable.jsx';
import RejectBookingDialog from '../components/Approvals/RejectBookingDialog.jsx';
import {
  APPROVAL_FILTERS,
  BOOKING_STATUS,
} from '../constants/bookingStatuses.js';
import { useAmenityBookingsStore } from '../store/useAmenityBookingsStore.js';

const getEmptyMessage = (activeFilter, hasSearchQuery) => {
  if (hasSearchQuery) {
    return 'No booking requests match your search.';
  }

  if (activeFilter === BOOKING_STATUS.PENDING) {
    return 'No pending booking requests.';
  }

  const filter = APPROVAL_FILTERS.find(
    (option) => option.value === activeFilter
  );
  return `No ${filter?.label.toLowerCase() ?? ''} booking requests.`;
};

export default function AmenityApprovalsPage() {
  const { amenity } = useOutletContext();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState(
    BOOKING_STATUS.PENDING
  );
  const [rejectionBooking, setRejectionBooking] = useState(null);
  const approvalRequests = useAmenityBookingsStore(
    (state) => state.approvalRequests
  );
  const approvalRequestKey = useAmenityBookingsStore(
    (state) => state.approvalRequestKey
  );
  const isApprovalsLoading = useAmenityBookingsStore(
    (state) => state.isApprovalsLoading
  );
  const approvalsError = useAmenityBookingsStore(
    (state) => state.approvalsError
  );
  const approvingBookingId = useAmenityBookingsStore(
    (state) => state.approvingBookingId
  );
  const rejectingBookingId = useAmenityBookingsStore(
    (state) => state.rejectingBookingId
  );
  const rejectionError = useAmenityBookingsStore(
    (state) => state.rejectionError
  );
  const fetchApprovalRequests = useAmenityBookingsStore(
    (state) => state.fetchApprovalRequests
  );
  const approveBookingRequest = useAmenityBookingsStore(
    (state) => state.approveBookingRequest
  );
  const rejectBookingRequest = useAmenityBookingsStore(
    (state) => state.rejectBookingRequest
  );
  const clearRejectionError = useAmenityBookingsStore(
    (state) => state.clearRejectionError
  );

  useEffect(() => {
    fetchApprovalRequests(amenity.id);
  }, [amenity.id, fetchApprovalRequests]);

  const counts = useMemo(
    () =>
      approvalRequests.reduce((statusCounts, booking) => {
        statusCounts[booking.status] =
          (statusCounts[booking.status] ?? 0) + 1;
        return statusCounts;
      }, {}),
    [approvalRequests]
  );

  const filteredRequests = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();

    return approvalRequests.filter((booking) => {
      if (booking.status !== activeFilter) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      return [
        booking.residentName,
        booking.residentFlat,
        booking.bookingTitle,
      ].some((value) => value?.toLowerCase().includes(normalizedQuery));
    });
  }, [activeFilter, approvalRequests, searchQuery]);

  const isLoading =
    approvalRequestKey !== amenity.id || isApprovalsLoading;

  return (
    <>
      <section className="overflow-hidden rounded-2xl border border-slate-100 bg-white">
        <div className="flex items-start gap-3 p-5 sm:p-6">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
            <ClipboardCheck className="h-5 w-5" />
          </span>
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600">
              Booking requests
            </p>
            <h2 className="mt-0.5 text-base font-extrabold text-slate-800">
              Approval dashboard
            </h2>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Review resident requests for {amenity.name}.
            </p>
          </div>
        </div>

        <ApprovalFilters
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          activeFilter={activeFilter}
          onFilterChange={setActiveFilter}
          counts={counts}
        />

        {approvalsError && (
          <div
            role="alert"
            className="mx-4 mt-4 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700 sm:mx-5"
          >
            {approvalsError}
          </div>
        )}

        {isLoading ? (
          <div className="px-6 py-14 text-center text-xs font-semibold text-slate-400">
            Loading booking requests...
          </div>
        ) : (
          <ApprovalTable
            bookings={filteredRequests}
            approvingBookingId={approvingBookingId}
            onApprove={approveBookingRequest}
            onReject={setRejectionBooking}
            emptyMessage={getEmptyMessage(
              activeFilter,
              Boolean(searchQuery.trim())
            )}
          />
        )}
      </section>

      {rejectionBooking && (
        <RejectBookingDialog
          booking={rejectionBooking}
          amenityName={amenity.name}
          isSubmitting={rejectingBookingId === rejectionBooking.id}
          submissionError={rejectionError}
          onClose={() => {
            clearRejectionError();
            setRejectionBooking(null);
          }}
          onReject={rejectBookingRequest}
        />
      )}
    </>
  );
}
