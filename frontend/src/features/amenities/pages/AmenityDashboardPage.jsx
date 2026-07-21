import React, { useEffect } from 'react';
import { CalendarDays } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';
import { longDate, todayISO } from '../../../lib/dates.js';
import BlockTimeModal from '../components/BlockTimeModal/index.jsx';
import BookingTimeline from '../components/BookingTimeline.jsx';
import CancelBookingDialog from '../components/CancelBookingDialog/index.jsx';
import CreateBookingModal from '../components/CreateBookingModal/index.jsx';
import EditBookingModal from '../components/EditBookingModal/index.jsx';
import TimelineActions from '../components/TimelineActions.jsx';
import TimelineLegend from '../components/TimelineLegend.jsx';
import TimelineSelectionCard from '../components/TimelineSelectionCard.jsx';
import { BOOKING_TIMELINE_STATE } from '../constants/bookingTimelineStates.js';
import { useAmenityBookingWorkflow } from '../hooks/useAmenityBookingWorkflow.js';
import { useBookingTimelineSelection } from '../hooks/useBookingTimelineSelection.js';
import { useAmenityBookingsStore } from '../store/useAmenityBookingsStore.js';

export default function AmenityDashboardPage() {
  const { amenity } = useOutletContext();
  const selectedDate = todayISO();
  const bookings = useAmenityBookingsStore((state) => state.bookings);
  const requestKey = useAmenityBookingsStore((state) => state.requestKey);
  const isLoading = useAmenityBookingsStore((state) => state.isLoading);
  const error = useAmenityBookingsStore((state) => state.error);
  const fetchBookings = useAmenityBookingsStore(
    (state) => state.fetchBookings
  );
  const expectedRequestKey = `${amenity.id}:${selectedDate}`;
  const hasBookings = bookings.some(
    (booking) => booking.state === BOOKING_TIMELINE_STATE.BOOKED
  );
  const {
    selectedSlot,
    selectedBooking,
    selectedState,
    selectSlot,
    selectBooking,
    clearSelection,
  } = useBookingTimelineSelection();
  const canCreateBooking =
    Boolean(selectedSlot) &&
    selectedState === BOOKING_TIMELINE_STATE.AVAILABLE;
  const {
    residents,
    isResidentsLoading,
    isSubmitting,
    modalError,
    isBookingModalOpen,
    isEditBookingModalOpen,
    isCancelBookingDialogOpen,
    isMaintenanceModalOpen,
    openBookingModal,
    openMaintenanceModal,
    closeModal,
    openCancelBookingDialog,
    closeCancelBookingDialog,
    createBooking,
    createBlockedSlot,
    updateBooking,
    cancelBooking,
  } = useAmenityBookingWorkflow();

  useEffect(() => {
    fetchBookings(amenity.id, selectedDate);
  }, [amenity.id, selectedDate, fetchBookings]);

  return (
    <>
      <section className="space-y-5 rounded-2xl border border-slate-100 bg-white p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
              <CalendarDays className="h-5 w-5" />
            </span>
            <div>
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600">
                Daily schedule
              </p>
              <h2 className="mt-0.5 text-base font-extrabold text-slate-800">
                Today&apos;s booking timeline
              </h2>
              <p className="mt-1 text-xs font-semibold text-slate-400">
                {longDate()}
              </p>
            </div>
          </div>

          <TimelineLegend />
        </div>

        <TimelineActions
          canCreateBooking={canCreateBooking}
          onCreateBooking={openBookingModal}
          onBlockTime={openMaintenanceModal}
        />

        {requestKey !== expectedRequestKey || isLoading ? (
          <div className="rounded-xl bg-slate-50 px-4 py-10 text-center text-xs font-semibold text-slate-400">
            Loading booking schedule...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-10 text-center text-xs font-bold text-rose-700">
            {error}
          </div>
        ) : (
          <div className="space-y-3">
            {!hasBookings && (
              <p className="rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-center text-xs font-bold text-emerald-700">
                No bookings scheduled today.
              </p>
            )}
            <BookingTimeline
              bookings={bookings}
              openingTime={amenity.openingTime}
              closingTime={amenity.closingTime}
              cleaningBuffer={amenity.cleaningBuffer}
              amenityId={amenity.id}
              selectedDate={selectedDate}
              selectedSlot={selectedSlot}
              selectedBooking={selectedBooking}
              onSelectSlot={selectSlot}
              onSelectBooking={selectBooking}
            />
            <TimelineSelectionCard
              amenityName={amenity.name}
              selectedSlot={selectedSlot}
              selectedBooking={selectedBooking}
              selectedState={selectedState}
              onClear={clearSelection}
            />
          </div>
        )}
      </section>

      {isBookingModalOpen && selectedSlot && (
        <CreateBookingModal
          amenity={amenity}
          selectedSlot={selectedSlot}
          residents={residents}
          isResidentsLoading={isResidentsLoading}
          isSubmitting={isSubmitting}
          submissionError={modalError}
          onClose={closeModal}
          onSubmit={createBooking}
        />
      )}

      {isMaintenanceModalOpen && (
        <BlockTimeModal
          amenity={amenity}
          selectedDate={selectedDate}
          selectedSlot={selectedSlot}
          isSubmitting={isSubmitting}
          submissionError={modalError}
          onClose={closeModal}
          onSubmit={createBlockedSlot}
        />
      )}

      {isEditBookingModalOpen &&
        !isCancelBookingDialogOpen &&
        selectedBooking && (
          <EditBookingModal
            amenity={amenity}
            booking={selectedBooking}
            residents={residents}
            isResidentsLoading={isResidentsLoading}
            isSubmitting={isSubmitting}
            submissionError={modalError}
            onClose={closeModal}
            onSubmit={updateBooking}
            onCancelBooking={openCancelBookingDialog}
          />
        )}

      {isCancelBookingDialogOpen && selectedBooking && (
        <CancelBookingDialog
          booking={selectedBooking}
          isSubmitting={isSubmitting}
          submissionError={modalError}
          onClose={closeCancelBookingDialog}
          onConfirm={cancelBooking}
        />
      )}
    </>
  );
}
