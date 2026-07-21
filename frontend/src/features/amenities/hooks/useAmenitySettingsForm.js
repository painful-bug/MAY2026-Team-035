import { useEffect, useMemo, useRef, useState } from 'react';
import {
  createAmenitySettingsFormValues,
  serializeAmenitySettings,
} from '../utils/amenitySettingsModel.js';
import { validateAmenitySettings } from '../utils/validateAmenitySettings.js';

export const useAmenitySettingsForm = (amenity, onSave) => {
  const initialValues = useMemo(
    () => createAmenitySettingsFormValues(amenity),
    [amenity]
  );
  const savedValuesRef = useRef(initialValues);
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    savedValuesRef.current = initialValues;
    setValues(initialValues);
    setErrors({});
  }, [initialValues]);

  const updateField = (field, value) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => {
      if (!current[field]) {
        return current;
      }

      const nextErrors = { ...current };
      delete nextErrors[field];
      return nextErrors;
    });
  };

  const toggleDay = (field, day) => {
    setValues((current) => ({
      ...current,
      [field]: current[field].includes(day)
        ? current[field].filter((item) => item !== day)
        : [...current[field], day],
    }));
  };

  const resetChanges = () => {
    setValues(savedValuesRef.current);
    setErrors({});
  };

  const submitSettings = async (event) => {
    event.preventDefault();
    const validationErrors = validateAmenitySettings(values);
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      return false;
    }

    const updatedAmenity = await onSave(serializeAmenitySettings(values));
    if (!updatedAmenity) {
      return false;
    }

    const savedValues = createAmenitySettingsFormValues(updatedAmenity);
    savedValuesRef.current = savedValues;
    setValues(savedValues);
    setErrors({});
    return true;
  };

  return {
    errors,
    isDirty: JSON.stringify(values) !== JSON.stringify(savedValuesRef.current),
    resetChanges,
    submitSettings,
    toggleDay,
    updateField,
    values,
  };
};
