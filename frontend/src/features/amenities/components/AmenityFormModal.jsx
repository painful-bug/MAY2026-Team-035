import React, { useEffect, useId } from 'react';
import { createPortal } from 'react-dom';
import { AMENITY_CATEGORIES } from '../constants/amenityCategories.js';
import { useAmenityForm } from '../hooks/useAmenityForm.js';
import AmenityFormField, {
  amenityInputClasses,
} from './AmenityFormField.jsx';
import AmenityImagePicker from './AmenityImagePicker.jsx';
import AmenityStatusToggle from './AmenityStatusToggle.jsx';
import BookingConfigurationSection from './BookingConfigurationSection.jsx';

export default function AmenityFormModal({
  onClose,
  onSubmit,
  isSubmitting,
  submissionError,
}) {
  const titleId = useId();
  const {
    errors,
    isProcessingImage,
    values,
    removeImage,
    selectImage,
    submitForm,
    updateBookingMode,
    updateField,
  } = useAmenityForm(onSubmit);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleEscape = (event) => {
      if (event.key === 'Escape' && !isSubmitting) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isSubmitting, onClose]);

  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget && !isSubmitting) {
      onClose();
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[999] flex items-start justify-center overflow-y-auto bg-slate-900/60 p-8 backdrop-blur-sm animate-fade-in"
      onMouseDown={handleBackdropClick}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="max-h-[calc(100vh-4rem)] w-full max-w-2xl overflow-y-auto rounded-3xl border border-slate-100 bg-white p-6 shadow-xl shadow-slate-100 animate-slide-up"
      >
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2
              id={titleId}
              className="text-lg font-extrabold tracking-tight text-slate-900"
            >
              Add Amenity
            </h2>
            <p className="mt-1 text-xs font-medium text-slate-400">
              Add the facility details residents will see.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="text-xs font-bold text-slate-400 transition-colors hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
        </div>

        <form onSubmit={submitForm} noValidate className="space-y-5">
          {submissionError && (
            <div
              role="alert"
              className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700"
            >
              {submissionError}
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <AmenityFormField label="Amenity Name" required error={errors.name}>
              <input
                type="text"
                autoFocus
                value={values.name}
                onChange={(event) => updateField('name', event.target.value)}
                placeholder="e.g. Badminton Court"
                aria-invalid={Boolean(errors.name)}
                className={`${amenityInputClasses} ${
                  errors.name ? 'border-rose-300 focus:border-rose-500' : ''
                }`}
              />
            </AmenityFormField>

            <AmenityFormField label="Category">
              <select
                value={values.category}
                onChange={(event) =>
                  updateField('category', event.target.value)
                }
                className={amenityInputClasses}
              >
                {AMENITY_CATEGORIES.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </AmenityFormField>
          </div>

          <AmenityFormField
            label="Description"
            required
            error={errors.description}
          >
            <textarea
              rows={3}
              value={values.description}
              onChange={(event) =>
                updateField('description', event.target.value)
              }
              placeholder="Describe the facility and its intended use."
              aria-invalid={Boolean(errors.description)}
              className={`${amenityInputClasses} resize-none ${
                errors.description
                  ? 'border-rose-300 focus:border-rose-500'
                  : ''
              }`}
            />
          </AmenityFormField>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <AmenityFormField
              label="Opening Time"
              required
              error={errors.openingTime}
            >
              <input
                type="time"
                value={values.openingTime}
                onChange={(event) =>
                  updateField('openingTime', event.target.value)
                }
                aria-invalid={Boolean(errors.openingTime)}
                className={`${amenityInputClasses} ${
                  errors.openingTime
                    ? 'border-rose-300 focus:border-rose-500'
                    : ''
                }`}
              />
            </AmenityFormField>

            <AmenityFormField
              label="Closing Time"
              required
              error={errors.closingTime}
            >
              <input
                type="time"
                value={values.closingTime}
                onChange={(event) =>
                  updateField('closingTime', event.target.value)
                }
                aria-invalid={Boolean(errors.closingTime)}
                className={`${amenityInputClasses} ${
                  errors.closingTime
                    ? 'border-rose-300 focus:border-rose-500'
                    : ''
                }`}
              />
            </AmenityFormField>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Status
              </p>
              <p className="mt-0.5 text-xs font-bold text-slate-700">
                {values.isActive ? 'Active' : 'Inactive'}
              </p>
            </div>
            <AmenityStatusToggle
              checked={values.isActive}
              onChange={(isActive) => updateField('isActive', isActive)}
              ariaLabel="Set amenity status"
              disabled={isSubmitting}
            />
          </div>

          <BookingConfigurationSection
            values={values}
            errors={errors}
            onFieldChange={updateField}
            onBookingModeChange={updateBookingMode}
          />

          <AmenityFormField label="Image Upload" error={errors.image}>
            <AmenityImagePicker
              image={values.image}
              isProcessing={isProcessingImage}
              onSelect={selectImage}
              onRemove={removeImage}
            />
          </AmenityFormField>

          <div className="flex justify-end border-t border-slate-100 pt-5">
            <button
              type="submit"
              disabled={isSubmitting || isProcessingImage}
              className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-all hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
            >
              {isSubmitting ? 'Adding Amenity...' : 'Add Amenity'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
