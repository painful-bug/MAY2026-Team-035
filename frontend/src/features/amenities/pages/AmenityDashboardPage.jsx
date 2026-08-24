import React, { useEffect, useState } from 'react';
import { CalendarDays } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fromISODate, localTodayISO, longDate } from '../../../lib/dates.js';
import { amenitiesApi } from '../amenitiesApi.js';
import BlockTimeModal from '../components/BlockTimeModal/index.jsx';
import BookingTimeline from '../components/BookingTimeline.jsx';
import CancelBookingDialog from '../components/CancelBookingDialog/index.jsx';
import CreateBookingModal from '../components/CreateBookingModal/index.jsx';
import TimelineActions from '../components/TimelineActions.jsx';
import TimelineLegend from '../components/TimelineLegend.jsx';
import TimelineSelectionCard from '../components/TimelineSelectionCard.jsx';
import { BOOKING_TIMELINE_STATE } from '../constants/bookingTimelineStates.js';

// The day timeline, over `GET /amenities/{id}/bookings` and the three writes a
// timeline can perform.
//
// **The day is chosen, not assumed.** It was fixed at `todayISO()` — UTC's
// today — so the page could only ever show one day, and east of UTC that day
// was the wrong one for most of the working morning. It defaults to the
// reader's own today and the picker moves it.
//
// **No availability check happens here any more.** `validateBookingSlot` walked
// a cached array before every create, which is a check-then-act that loses the
// race between two admins booking the last place. Overlap is guarded by the
// database in two places — an `EXCLUDE USING gist` constraint and a `BEFORE`
// trigger holding an advisory lock — so a taken slot comes back as a `409` with
// the message the form already renders, and the answer is true at the moment it
// is given rather than at the moment the page loaded.
//
// The cleaning buffer is still drawn client-side from each booking's end and
// the amenity's buffer: the API deliberately does not send buffers as blocks,
// because one block with two sources is one block that can disagree with itself.
//
// **There is no edit path**, and that is an API fact rather than a layout
// choice — see `TimelineActions`.

export default function AmenityDashboardPage() {
  const { amenity } = useOutletContext();
  const queryClient = useQueryClient();
  // LOCAL today, not `todayISO()`. That helper converts to UTC first, so from
  // 05:30 IST onwards this page opened on TOMORROW's schedule — empty, with
  // today's bookings nowhere on it — and there was no way to navigate back to
  // the day the admin meant. The picker below is that way.
  const [selectedDate, setSelectedDate] = useState(localTodayISO);
  const isToday = selectedDate === localTodayISO();

  const [selectedSlot, setSelectedSlot] = useState(null);
  const [selectedBooking, setSelectedBooking] = useState(null);
  const [selectedState, setSelectedState] = useState(null);
  const [openModal, setOpenModal] = useState(null);

  const bookings = useQuery({
    queryKey: ['amenities', amenity.id, 'bookings', selectedDate],
    queryFn: () =>
      amenitiesApi.bookings(amenity.id, {
        date: selectedDate,
        pageSize: 200,
      }),
  });

  // Only fetched once a modal that needs it is open. It is a read of the
  // ADMIN-guarded dashboard snapshot, and a timeline nobody is booking against
  // has no reason to ask for the whole community.
  const residents = useQuery({
    queryKey: ['amenities', 'bookable-residents'],
    queryFn: () => amenitiesApi.bookableResidents(),
    enabled: openModal === 'create',
  });

  const clearSelection = () => {
    setSelectedSlot(null);
    setSelectedBooking(null);
    setSelectedState(null);
  };

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['amenities', amenity.id] });
    setOpenModal(null);
    clearSelection();
  };

  const createBooking = useMutation({
    mutationFn: (payload) => amenitiesApi.createBooking(amenity.id, payload),
    onSuccess: invalidate,
  });
  const blockSlot = useMutation({
    mutationFn: (payload) => amenitiesApi.blockSlot(amenity.id, payload),
    onSuccess: invalidate,
  });
  const cancelBooking = useMutation({
    mutationFn: (payload) => amenitiesApi.cancelDays(payload),
    onSuccess: invalidate,
  });

  const isSubmitting =
    createBooking.isPending || blockSlot.isPending || cancelBooking.isPending;

  const closeModal = () => {
    if (isSubmitting) {
      return;
    }

    createBooking.reset();
    blockSlot.reset();
    cancelBooking.reset();
    setOpenModal(null);
  };

  // A selection belongs to the day it was made on: keeping it across a date
  // change would offer "Cancel booking" for a row that is no longer drawn.
  useEffect(() => {
    clearSelection();
    setOpenModal(null);
  }, [amenity.id, selectedDate]);

  const items = bookings.data?.items || [];
  const hasBookings = items.some(
    (booking) => booking.state === BOOKING_TIMELINE_STATE.BOOKED
  );
  const canCreateBooking =
    Boolean(selectedSlot) && selectedState === BOOKING_TIMELINE_STATE.AVAILABLE;
  // A block is cancelled the same way a booking is — `POST
  // /amenity-bookings/cancel` takes occurrence ids and does not care which kind
  // of occupancy they are — but the cleaning buffer is a render-time artefact
  // with no row behind it, so it is not offered.
  const canCancelBooking =
    Boolean(selectedBooking) &&
    selectedState !== BOOKING_TIMELINE_STATE.CLEANING_BUFFER;

  const handleSelectSlot = (slot) => {
    setSelectedSlot(slot);
    setSelectedBooking(null);
    setSelectedState(BOOKING_TIMELINE_STATE.AVAILABLE);
  };

  const handleSelectBooking = (booking) => {
    setSelectedSlot(null);
    setSelectedBooking(booking);
    setSelectedState(booking.state);
  };

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
                {isToday
                  ? "Today's booking timeline"
                  : 'Booking timeline'}
              </h2>
              <p className="mt-1 text-xs font-semibold text-slate-400">
                {longDate(fromISODate(selectedDate))}
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2">
              <label
                htmlFor="timeline-date"
                className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500"
              >
                Date
              </label>
              <input
                id="timeline-date"
                type="date"
                value={selectedDate}
                onChange={(event) =>
                  setSelectedDate(event.target.value || localTodayISO())
                }
                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
              />
              {!isToday && (
                <button
                  type="button"
                  onClick={() => setSelectedDate(localTodayISO())}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 transition-colors hover:border-indigo-200 hover:text-indigo-600"
                >
                  Today
                </button>
              )}
            </div>

            <TimelineLegend />
          </div>
        </div>

        <TimelineActions
          canCreateBooking={canCreateBooking}
          canCancelBooking={canCancelBooking}
          onCreateBooking={() => setOpenModal('create')}
          onBlockTime={() => setOpenModal('block')}
          onCancelBooking={() => setOpenModal('cancel')}
        />

        {bookings.isPending ? (
          <div className="rounded-xl bg-slate-50 px-4 py-10 text-center text-xs font-semibold text-slate-400">
            Loading booking schedule...
          </div>
        ) : bookings.error ? (
          <div className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-10 text-center">
            <p role="alert" className="text-xs font-bold text-rose-700">
              {bookings.error.message}
            </p>
            <button
              type="button"
              onClick={() => bookings.refetch()}
              className="mt-3 rounded-xl border border-rose-100 bg-white px-4 py-2 text-xs font-bold text-rose-700 hover:bg-rose-50"
            >
              Try again
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {!hasBookings && (
              <p className="rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-center text-xs font-bold text-emerald-700">
                {isToday
                  ? 'No bookings scheduled today.'
                  : `No bookings scheduled on ${longDate(fromISODate(selectedDate))}.`}
              </p>
            )}
            <BookingTimeline
              bookings={items}
              openingTime={amenity.openingTime}
              closingTime={amenity.closingTime}
              cleaningBuffer={amenity.cleaningBuffer}
              amenityId={amenity.id}
              selectedDate={selectedDate}
              selectedSlot={selectedSlot}
              selectedBooking={selectedBooking}
              onSelectSlot={handleSelectSlot}
              onSelectBooking={handleSelectBooking}
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

      {openModal === 'create' && selectedSlot && (
        <CreateBookingModal
          amenity={amenity}
          selectedSlot={selectedSlot}
          residents={residents.data || []}
          isResidentsLoading={residents.isPending}
          isSubmitting={createBooking.isPending}
          submissionError={
            createBooking.error?.message || residents.error?.message
          }
          onClose={closeModal}
          onSubmit={(values) =>
            createBooking.mutateAsync({
              // The MEMBERSHIP id: the form's resident list is keyed by it, and
              // the flat is resolved from that residency rather than sent.
              membershipId: values.residentId,
              bookingTitle: values.bookingTitle,
              bookingType: values.bookingType,
              date: values.date,
              startTime: values.startTime,
              endTime: values.endTime,
              isPrivateBooking: values.isPrivateBooking,
              guestCount: Number(values.guestCount) || 0,
              guests: (values.guests || [])
                .filter((guest) => guest.name?.trim())
                .map((guest) => ({
                  name: guest.name.trim(),
                  phone: guest.contactNumber?.trim() || null,
                })),
              notes: values.notes,
              // `null` is "use the amenity's fee" and `0` is "free". They are
              // different answers and the API keeps them different, so an empty
              // field must not collapse to zero.
              chargeOverride:
                values.chargeOverride === '' || values.chargeOverride == null
                  ? null
                  : Number(values.chargeOverride),
            }).catch(() => null)
          }
        />
      )}

      {openModal === 'block' && (
        <BlockTimeModal
          amenity={amenity}
          selectedDate={selectedDate}
          selectedSlot={selectedSlot}
          isSubmitting={blockSlot.isPending}
          submissionError={blockSlot.error?.message}
          onClose={closeModal}
          onSubmit={(values) =>
            blockSlot.mutateAsync({
              reason: values.reason.trim(),
              date: values.date,
              startTime: values.startTime,
              endTime: values.endTime,
              department: values.department || null,
              notes: values.notes?.trim() || null,
            }).catch(() => null)
          }
        />
      )}

      {openModal === 'cancel' && selectedBooking && (
        <CancelBookingDialog
          booking={selectedBooking}
          isSubmitting={cancelBooking.isPending}
          submissionError={cancelBooking.error?.message}
          onClose={closeModal}
          onConfirm={(bookingId, cancellation) =>
            cancelBooking.mutateAsync({
              // One day, by occurrence id. The call is all-or-nothing across the
              // ids it is given, and an admin cancelling from the timeline is
              // cancelling the day they clicked.
              occurrenceIds: [bookingId],
              reasonCode: cancellation.reason,
              reason: cancellation.details?.trim() || null,
            }).catch(() => null)
          }
        />
      )}
    </>
  );
}
