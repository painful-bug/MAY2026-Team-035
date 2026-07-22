import React, { useState } from 'react';
import { genId } from '../../../../lib/ids.js';
import { getBookingTypeLabel } from '../../constants/bookingFormOptions.js';
import BookingDetails from '../CreateBookingModal/BookingDetails.jsx';
import ChargeOverride from '../CreateBookingModal/ChargeOverride.jsx';
import GuestList from '../CreateBookingModal/GuestList.jsx';
import InternalNotes from '../CreateBookingModal/InternalNotes.jsx';
import ResidentSearch from '../CreateBookingModal/ResidentSearch.jsx';
import { validateBooking } from '../CreateBookingModal/validation.js';
import ModalFooter from './ModalFooter.jsx';
import ModalLayout from './ModalLayout.jsx';

const createInitialValues = (booking, selectedSlot) => ({
  residentId: booking?.residentId ?? '',
  bookingType: booking?.bookingType ?? '',
  isPrivateBooking: Boolean(booking?.isPrivateBooking),
  guestCount: String(booking?.guestCount ?? 0),
  guests: (booking?.guests ?? []).map((guest) => ({
    ...guest,
    id: guest.id ?? genId('guest'),
  })),
  internalNotes: booking?.notes ?? '',
  chargeOverride:
    booking?.chargeOverride == null ? '' : String(booking.chargeOverride),
  date: booking?.date ?? selectedSlot?.date ?? '',
  startTime: booking?.startTime ?? selectedSlot?.startTime ?? '',
  endTime: booking?.endTime ?? selectedSlot?.endTime ?? '',
});

export default function BookingFormModal({
  mode,
  amenity,
  selectedSlot,
  booking = null,
  residents,
  isResidentsLoading,
  isSubmitting,
  submissionError,
  onClose,
  onSubmit,
  onCancelBooking,
}) {
  const isEditing = mode === 'edit';
  const [values, setValues] = useState(() =>
    createInitialValues(booking, selectedSlot)
  );
  const [errors, setErrors] = useState({});

  const updateField = (field, value) => {
    setValues((currentValues) => ({ ...currentValues, [field]: value }));
    setErrors((currentErrors) => ({ ...currentErrors, [field]: undefined }));
  };

  const addGuest = () => {
    setValues((currentValues) => ({
      ...currentValues,
      guests: [
        ...currentValues.guests,
        { id: genId('guest'), name: '', contactNumber: '' },
      ],
    }));
  };

  const updateGuest = (index, field, value) => {
    setValues((currentValues) => ({
      ...currentValues,
      guests: currentValues.guests.map((guest, guestIndex) =>
        guestIndex === index ? { ...guest, [field]: value } : guest
      ),
    }));
  };

  const removeGuest = (index) => {
    setValues((currentValues) => ({
      ...currentValues,
      guests: currentValues.guests.filter(
        (_guest, guestIndex) => guestIndex !== index
      ),
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const validationErrors = validateBooking(values);
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    const resident = residents.find(
      (residentRecord) => residentRecord.id === values.residentId
    );
    const residentName =
      resident?.name ??
      (booking?.residentId === values.residentId
        ? booking.residentName
        : null);

    if (!residentName) {
      setErrors((currentErrors) => ({
        ...currentErrors,
        residentId: 'Select a resident.',
      }));
      return;
    }

    await onSubmit({
      amenityId: amenity.id,
      residentId: values.residentId,
      residentName,
      bookingTitle: isEditing
        ? booking.bookingTitle
        : getBookingTypeLabel(values.bookingType),
      date: values.date,
      startTime: values.startTime,
      endTime: values.endTime,
      bookingType: values.bookingType,
      isPrivateBooking: amenity.allowPrivateBooking
        ? values.isPrivateBooking
        : false,
      guestCount: values.guestCount,
      guests: values.guests.map(({ id: _id, ...guest }) => guest),
      notes: values.internalNotes.trim() || null,
      chargeOverride: values.chargeOverride,
      openingTime: amenity.openingTime,
      closingTime: amenity.closingTime,
      cleaningBuffer: amenity.cleaningBuffer,
    });
  };

  return (
    <ModalLayout
      title={
        isEditing ? 'Edit Booking' : 'Create Booking (Admin Override)'
      }
      description={
        isEditing
          ? 'Update the booking details and schedule.'
          : 'Create a confirmed booking for the selected available slot.'
      }
      onClose={onClose}
      isBusy={isSubmitting}
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        {submissionError && (
          <div
            role="alert"
            className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700"
          >
            {submissionError}
          </div>
        )}

        <ResidentSearch
          residents={residents}
          value={values.residentId}
          initialResidentName={booking?.residentName}
          onChange={(residentId) => updateField('residentId', residentId)}
          error={errors.residentId}
          isLoading={isResidentsLoading}
        />
        <BookingDetails
          amenity={amenity}
          slot={selectedSlot}
          values={values}
          errors={errors}
          isEditing={isEditing}
          onChange={updateField}
        />
        <GuestList
          guests={values.guests}
          onAdd={addGuest}
          onChange={updateGuest}
          onRemove={removeGuest}
        />
        <ChargeOverride
          value={values.chargeOverride}
          error={errors.chargeOverride}
          onChange={(chargeOverride) =>
            updateField('chargeOverride', chargeOverride)
          }
        />
        <InternalNotes
          value={values.internalNotes}
          onChange={(internalNotes) =>
            updateField('internalNotes', internalNotes)
          }
        />
        <ModalFooter
          onCancel={onClose}
          onSecondaryAction={isEditing ? onCancelBooking : undefined}
          secondaryLabel="Cancel Booking"
          isSubmitting={isSubmitting}
          submitLabel={isEditing ? 'Save Changes' : 'Create Booking'}
          submittingLabel={
            isEditing ? 'Saving Changes...' : 'Creating Booking...'
          }
        />
      </form>
    </ModalLayout>
  );
}
