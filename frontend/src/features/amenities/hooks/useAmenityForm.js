import { useEffect, useRef, useState } from 'react';
import { AMENITY_CATEGORIES } from '../constants/amenityCategories.js';
import { BOOKING_MODE } from '../constants/bookingModes.js';
import { validateAmenityForm } from '../utils/validateAmenityForm.js';

const createInitialValues = () => ({
  name: '',
  description: '',
  category: AMENITY_CATEGORIES[0],
  capacity: '',
  bookingMode: '',
  allowPrivateBooking: false,
  requireApproval: false,
  cleaningBuffer: '0',
  maxBookingsPerResident: '',
  openingTime: '',
  closingTime: '',
  isActive: true,
  image: '',
});

export const useAmenityForm = (onSubmit) => {
  const [values, setValues] = useState(createInitialValues);
  const [errors, setErrors] = useState({});
  const imageReaderRef = useRef(null);

  useEffect(
    () => () => {
      if (imageReaderRef.current?.readyState === FileReader.LOADING) {
        imageReaderRef.current.abort();
      }
    },
    []
  );

  const updateField = (field, value) => {
    setValues((currentValues) => ({ ...currentValues, [field]: value }));
    setErrors((currentErrors) => {
      if (!currentErrors[field]) {
        return currentErrors;
      }

      const nextErrors = { ...currentErrors };
      delete nextErrors[field];
      return nextErrors;
    });
  };

  const selectImage = (file) => {
    if (!file) {
      return;
    }

    if (!file.type.startsWith('image/')) {
      setErrors((currentErrors) => ({
        ...currentErrors,
        image: 'Choose a valid image file.',
      }));
      return;
    }

    const reader = new FileReader();
    imageReaderRef.current = reader;
    reader.addEventListener('load', () => {
      updateField('image', String(reader.result));
    });
    reader.addEventListener('error', () => {
      setErrors((currentErrors) => ({
        ...currentErrors,
        image: 'The image could not be previewed.',
      }));
    });
    reader.readAsDataURL(file);
  };

  const removeImage = () => {
    updateField('image', '');
  };

  const updateBookingMode = (bookingMode) => {
    setValues((currentValues) => ({
      ...currentValues,
      bookingMode,
      capacity:
        bookingMode === BOOKING_MODE.EXCLUSIVE
          ? ''
          : currentValues.capacity,
      allowPrivateBooking:
        bookingMode === BOOKING_MODE.HYBRID
          ? currentValues.allowPrivateBooking
          : false,
    }));
    setErrors((currentErrors) => {
      const nextErrors = { ...currentErrors };
      delete nextErrors.bookingMode;
      delete nextErrors.capacity;
      return nextErrors;
    });
  };

  const submitForm = async (event) => {
    event.preventDefault();
    const validationErrors = validateAmenityForm(values);
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      return false;
    }

    const supportsSharedCapacity =
      values.bookingMode === BOOKING_MODE.SHARED ||
      values.bookingMode === BOOKING_MODE.HYBRID;

    return onSubmit({
      ...values,
      name: values.name.trim(),
      description: values.description.trim(),
      capacity: supportsSharedCapacity ? Number(values.capacity) : null,
      allowPrivateBooking:
        values.bookingMode === BOOKING_MODE.HYBRID
          ? values.allowPrivateBooking
          : false,
      cleaningBuffer:
        values.cleaningBuffer === '' ? 0 : Number(values.cleaningBuffer),
      maxBookingsPerResident:
        values.maxBookingsPerResident === ''
          ? null
          : Number(values.maxBookingsPerResident),
    });
  };

  return {
    errors,
    values,
    removeImage,
    selectImage,
    submitForm,
    updateBookingMode,
    updateField,
  };
};
