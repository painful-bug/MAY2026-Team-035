import { useEffect, useRef, useState } from 'react';
import { AMENITY_CATEGORIES } from '../constants/amenityCategories.js';
import { BOOKING_MODE } from '../constants/bookingModes.js';
import { downscaleImageFile } from '../utils/downscaleImage.js';
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
  const [isProcessingImage, setIsProcessingImage] = useState(false);
  const isMountedRef = useRef(true);

  useEffect(
    () => () => {
      isMountedRef.current = false;
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

  // The picture is downscaled HERE rather than at submit time, because what
  // the admin previews has to be what is stored: the amenity image ships as a
  // base64 data URL inside `amenities.image_url` and the write endpoint refuses
  // anything over ~100KB, so a full-size camera photo has to lose its pixels
  // before it can be part of the form's value at all. `downscaleImageFile`
  // throws a sentence written for the admin; it is shown as the field's error.
  const selectImage = async (file) => {
    if (!file) {
      return;
    }

    setIsProcessingImage(true);

    try {
      const image = await downscaleImageFile(file);

      if (isMountedRef.current) {
        updateField('image', image);
      }
    } catch (error) {
      if (isMountedRef.current) {
        setErrors((currentErrors) => ({
          ...currentErrors,
          image:
            error instanceof Error
              ? error.message
              : 'The image could not be prepared.',
        }));
      }
    } finally {
      if (isMountedRef.current) {
        setIsProcessingImage(false);
      }
    }
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

    // The picture is still being resized; submitting now would save the
    // amenity without it and give no hint why.
    if (isProcessingImage) {
      return false;
    }

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
    isProcessingImage,
    values,
    removeImage,
    selectImage,
    submitForm,
    updateBookingMode,
    updateField,
  };
};
