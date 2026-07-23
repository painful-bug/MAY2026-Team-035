import { normalizeAmenityRecord } from '../utils/amenitySettingsModel.js';

export const AMENITIES_STORAGE_KEY = 'homebandhu-amenities';
const AMENITIES_VERSION_KEY = 'homebandhu-amenities-version';
const AMENITIES_VERSION = '2';

let memoryFallback = null;

const cloneAmenities = (amenities) =>
  amenities.map((amenity) => normalizeAmenityRecord(amenity));

const getLocalStorage = () => {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.localStorage;
};

const persistAmenities = (amenities) => {
  const records = cloneAmenities(amenities);
  const storage = getLocalStorage();

  if (storage) {
    storage.setItem(AMENITIES_STORAGE_KEY, JSON.stringify(records));
    storage.setItem(AMENITIES_VERSION_KEY, AMENITIES_VERSION);
  } else {
    memoryFallback = records;
  }

  return cloneAmenities(records);
};

export const loadAmenities = (initialAmenities) => {
  const storage = getLocalStorage();

  if (!storage) {
    if (memoryFallback === null) {
      memoryFallback = cloneAmenities(initialAmenities);
    }

    return cloneAmenities(memoryFallback);
  }

  const persistedValue = storage.getItem(AMENITIES_STORAGE_KEY);

  if (persistedValue === null) {
    return persistAmenities(initialAmenities);
  }

  try {
    const amenities = JSON.parse(persistedValue);

    if (!Array.isArray(amenities)) {
      throw new TypeError('Persisted amenities must be an array.');
    }

    if (storage.getItem(AMENITIES_VERSION_KEY) !== AMENITIES_VERSION) {
      return persistAmenities(amenities);
    }

    return cloneAmenities(amenities);
  } catch {
    return persistAmenities(initialAmenities);
  }
};

export const saveAmenities = (amenities) => persistAmenities(amenities);
