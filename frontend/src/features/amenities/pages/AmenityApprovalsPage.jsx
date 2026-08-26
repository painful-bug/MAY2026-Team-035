import React, { useMemo, useState } from 'react';
import { ClipboardCheck } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { amenitiesApi } from '../amenitiesApi.js';
import { QUERY_POLICIES, PAGINATED } from '../../../lib/api/queryClient';
import ApprovalFilters from '../components/Approvals/ApprovalFilters.jsx';
import ApprovalTable from '../components/Approvals/ApprovalTable.jsx';
import RejectBookingDialog from '../components/Approvals/RejectBookingDialog.jsx';
import {
  APPROVAL_FILTERS,
  BOOKING_STATUS,
} from '../constants/bookingStatuses.js';

// The approvals queue, over `GET /amenities/{id}/approvals` and the two
// decisions behind it.
//
// **The status filter is now the server's `status` parameter**, not a
// `.filter()` over everything the browser happened to be holding. The search
// box stays client-side: the endpoint has no `q`, and a resident-name search
// invented here over one page would be a search that quietly misses people.
// It is scoped to the loaded page and the empty message says which.
//
// One row is one REQUEST. The demo produced one row per day, so a three-day
// booking appeared three times and could be approved on Monday and rejected on
// Tuesday; the API groups the series and `dayCount` says how much one click
// covers. Both decisions therefore take `bookingSeriesId`, never the row's own
// `id` — see `amenitiesApi.approve`.

const PAGE_SIZE = 50;

const getEmptyMessage = (activeFilter, hasSearchQuery) => {
  if (hasSearchQuery) {
    return 'No booking requests on this page match your search.';
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
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState(BOOKING_STATUS.PENDING);
  const [rejectionRequest, setRejectionRequest] = useState(null);

  const approvals = useQuery({
    queryKey: ['amenities', amenity.id, 'approvals', activeFilter],
    queryFn: () =>
      amenitiesApi.approvals(amenity.id, {
        status: activeFilter,
        pageSize: PAGE_SIZE,
      }),
    ...QUERY_POLICIES.list,
    ...PAGINATED,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['amenities', amenity.id] });

  const approve = useMutation({
    mutationFn: (seriesId) => amenitiesApi.approve(seriesId),
    onSuccess: invalidate,
  });

  const reject = useMutation({
    // `reasonCode` is the machine value the database checks; `reason` is the
    // free text that `other` requires and that everything else may omit.
    mutationFn: ({ seriesId, rejection }) =>
      amenitiesApi.reject(seriesId, {
        reasonCode: rejection.reason,
        reason: rejection.otherReason?.trim() || null,
        notifyResident: rejection.notifyResident,
      }),
    onSuccess: invalidate,
  });

  const requests = useMemo(() => approvals.data?.items || [], [approvals.data]);

  const filteredRequests = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();

    if (!normalizedQuery) {
      return requests;
    }

    return requests.filter((request) =>
      [request.residentName, request.residentFlat, request.bookingTitle].some(
        (value) => value?.toLowerCase().includes(normalizedQuery)
      )
    );
  }, [requests, searchQuery]);

  // Switching tabs makes an open dialog describe a request that is no longer on
  // screen, and leaves a failure message attached to nothing. Both are cleared
  // where the switch happens rather than in an effect that would have to list
  // the mutations as dependencies to say so.
  const changeFilter = (filter) => {
    setRejectionRequest(null);
    approve.reset();
    reject.reset();
    setActiveFilter(filter);
  };

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
              Review resident requests for {amenity.name}. One row is one
              request — approving it approves every day of it.
            </p>
          </div>
        </div>

        <ApprovalFilters
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          activeFilter={activeFilter}
          onFilterChange={changeFilter}
          counts={{ [activeFilter]: approvals.data?.total }}
        />

        {approve.error && (
          <div
            role="alert"
            className="mx-4 mt-4 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700 sm:mx-5"
          >
            {approve.error.message}
          </div>
        )}

        {approvals.isPending ? (
          <div className="px-6 py-14 text-center text-xs font-semibold text-slate-400">
            Loading booking requests...
          </div>
        ) : approvals.error ? (
          <div className="px-6 py-14 text-center">
            <p role="alert" className="text-xs font-bold text-rose-700">
              {approvals.error.message}
            </p>
            <button
              type="button"
              onClick={() => approvals.refetch()}
              className="mt-3 rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
            >
              Try again
            </button>
          </div>
        ) : (
          <>
            <ApprovalTable
              bookings={filteredRequests}
              approvingSeriesId={approve.isPending ? approve.variables : null}
              onApprove={(seriesId) => approve.mutate(seriesId)}
              onReject={setRejectionRequest}
              emptyMessage={getEmptyMessage(
                activeFilter,
                Boolean(searchQuery.trim())
              )}
            />
            {approvals.data?.hasMore && (
              <p className="border-t border-slate-50 px-6 py-3 text-[11px] font-semibold text-slate-400">
                Showing the first {PAGE_SIZE} of {approvals.data.total} requests
                in this view.
              </p>
            )}
          </>
        )}
      </section>

      {rejectionRequest && (
        <RejectBookingDialog
          booking={rejectionRequest}
          amenityName={amenity.name}
          isSubmitting={reject.isPending}
          submissionError={reject.error?.message}
          onClose={() => {
            reject.reset();
            setRejectionRequest(null);
          }}
          onReject={async (seriesId, rejection) => {
            try {
              return await reject.mutateAsync({ seriesId, rejection });
            } catch {
              return null;
            }
          }}
        />
      )}
    </>
  );
}
