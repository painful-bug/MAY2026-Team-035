import React, { useState } from 'react';
import ModalFooter from '../booking/ModalFooter.jsx';
import ModalLayout from '../booking/ModalLayout.jsx';
import BlockTimeDetails from './BlockTimeDetails.jsx';
import { getInitialBlockTime, validateBlockedSlot } from './validation.js';

export default function BlockTimeModal({
  amenity,
  selectedDate,
  selectedSlot,
  isSubmitting,
  submissionError,
  onClose,
  onSubmit,
}) {
  const initialTime = getInitialBlockTime(amenity, selectedSlot);
  const [values, setValues] = useState({
    reason: '',
    department: '',
    startTime: initialTime.startTime,
    endTime: initialTime.endTime,
    notes: '',
  });
  const [errors, setErrors] = useState({});

  const updateField = (field, value) => {
    setValues((currentValues) => ({ ...currentValues, [field]: value }));
    setErrors((currentErrors) => ({ ...currentErrors, [field]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const validationErrors = validateBlockedSlot(values);
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    await onSubmit({
      amenityId: amenity.id,
      date: selectedDate,
      startTime: values.startTime,
      endTime: values.endTime,
      reason: values.reason,
      department: values.department,
      notes: values.notes,
      openingTime: amenity.openingTime,
      closingTime: amenity.closingTime,
      cleaningBuffer: amenity.cleaningBuffer,
    });
  };

  return (
    <ModalLayout
      title="Block Out Time / Maintenance"
      description="Create an administrative block on this amenity timeline."
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

        <BlockTimeDetails
          amenity={amenity}
          date={selectedDate}
          values={values}
          errors={errors}
          onChange={updateField}
        />
        <ModalFooter
          onCancel={onClose}
          isSubmitting={isSubmitting}
          submitLabel="Block Time"
          submittingLabel="Blocking Time..."
        />
      </form>
    </ModalLayout>
  );
}
