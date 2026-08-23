import { getDashboardSnapshot } from '../../../lib/dashboard/dashboardApi.js';
import { api } from '../../../lib/api/client.js';
import {
  createAmenitySettingsFormValues,
  mergeAmenitySettings,
  normalizeAmenityRecord,
} from '../utils/amenitySettingsModel.js';
import { validateAmenitySettings } from '../utils/validateAmenitySettings.js';

const cloneAmenity = (amenity) => normalizeAmenityRecord(amenity);

// A snapshot without `amenities` must read as an empty catalogue, not a
// TypeError: the snapshot endpoint is shared surface under active backend
// work, and this file is what turns its failures into the page's error state
// (an `ApiError` from the 500 → `useAmenitiesStore.error` → "Try again",
// which calls straight back through here and genuinely refetches).
const readAmenities = async () =>
  ((await getDashboardSnapshot()).amenities ?? []).map(normalizeAmenityRecord);

const normalizeBookingConfiguration = (amenityData, currentAmenity = {}) => {
  const bookingMode = amenityData.bookingMode ?? currentAmenity.bookingMode;
  const capacity = amenityData.capacity ?? currentAmenity.capacity;
  const privateBooking =
    amenityData.allowPrivateBooking ?? currentAmenity.allowPrivateBooking;
  const approval =
    amenityData.requireApproval ?? currentAmenity.requireApproval ?? false;
  const cleaningBuffer =
    amenityData.cleaningBuffer ?? currentAmenity.cleaningBuffer ?? 0;
  const bookingLimit =
    amenityData.maxBookingsPerResident ??
    currentAmenity.maxBookingsPerResident;

  return {
    bookingMode,
    capacity: capacity === '' || capacity == null ? null : Number(capacity),
    allowPrivateBooking: Boolean(privateBooking),
    requireApproval: Boolean(approval),
    cleaningBuffer: Number(cleaningBuffer) || 0,
    maxBookingsPerResident:
      bookingLimit === '' || bookingLimit == null ? null : Number(bookingLimit),
  };
};

const findAmenityIndex = (amenities, amenityId) => {
  const amenityIndex = amenities.findIndex(
    (amenity) => amenity.id === amenityId
  );

  if (amenityIndex === -1) {
    throw new Error('Amenity not found.');
  }

  return amenityIndex;
};

export const getAmenities = async () => readAmenities();

export const getAmenityById = async (amenityId) => {
  const amenities = await readAmenities();
  const amenity = amenities.find((item) => item.id === amenityId);
  return amenity ? cloneAmenity(amenity) : null;
};

export const createAmenity = async (amenityData) => {
  const created = await api('/dashboard/amenities', {
    method: 'POST',
    body: JSON.stringify(toAmenityWrite(amenityData)),
  });
  return (await getAmenityById(created.id));
};

export const updateAmenity = async (amenityId, amenityData, currentAmenity) => {
  if (!currentAmenity) {
    const amenities = await readAmenities();
    currentAmenity = amenities[findAmenityIndex(amenities, amenityId)];
  }
  const isActive = amenityData.isActive ?? currentAmenity.isActive;
  const updatedAmenity = normalizeAmenityRecord({
    ...currentAmenity,
    ...amenityData,
    ...normalizeBookingConfiguration(amenityData, currentAmenity),
    id: currentAmenity.id,
    status: isActive ? 'Active' : 'Inactive',
    isActive,
  });

  await api(`/dashboard/amenities/${amenityId}`, {
    method: 'PUT',
    body: JSON.stringify(toAmenityWrite(updatedAmenity)),
  });
  return getAmenityById(amenityId);
};

export const removeAmenity = async (amenityId) => {
  const amenities = await readAmenities();
  findAmenityIndex(amenities, amenityId);
  await api(`/dashboard/amenities/${amenityId}`, { method: 'DELETE' });
  return amenityId;
};

export const setAmenityActiveStatus = async (currentAmenity) => {
  const isActive = !currentAmenity.isActive;
  return updateAmenity(
    currentAmenity.id,
    { ...currentAmenity, status: isActive ? 'Active' : 'Inactive', isActive },
    currentAmenity
  );
};

export const updateAmenitySettings = async (amenityId, settings) => {
  const amenities = await readAmenities();
  const amenityIndex = findAmenityIndex(amenities, amenityId);
  const updatedAmenity = mergeAmenitySettings(
    amenities[amenityIndex],
    settings
  );
  const validationErrors = validateAmenitySettings(
    createAmenitySettingsFormValues(updatedAmenity)
  );

  if (Object.keys(validationErrors).length > 0) {
    throw new Error(Object.values(validationErrors)[0]);
  }

  return updateAmenity(amenityId, updatedAmenity);
};

const toAmenityWrite = (amenity) => ({
  name: amenity.name,
  description: amenity.description ?? '',
  category: amenity.category ?? 'Utility',
  location: amenity.location ?? '',
  capacity: amenity.capacity == null || amenity.capacity === '' ? null : Number(amenity.capacity),
  booking_mode: amenity.bookingMode ?? 'Exclusive',
  approval_required: Boolean(amenity.requireApproval),
  hourly_rate: Number(amenity.hourlyRate ?? 0),
  is_active: amenity.isActive ?? true,
  ...(amenity.image ? { image: amenity.image } : {}),
  ...(amenity.openingHours === ''
    ? {}
    : {
        opening_time: amenity.openingTime,
        closing_time: amenity.closingTime,
      }),
});
