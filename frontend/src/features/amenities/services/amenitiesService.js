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

export const updateAmenity = async (amenityId, amenityData) => {
  const amenities = await readAmenities();
  const amenityIndex = findAmenityIndex(amenities, amenityId);
  const currentAmenity = amenities[amenityIndex];
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

export const setAmenityActiveStatus = async (amenityId) => {
  const amenities = await readAmenities();
  const amenityIndex = findAmenityIndex(amenities, amenityId);
  const currentAmenity = amenities[amenityIndex];
  const isActive = !currentAmenity.isActive;
  const updatedAmenity = {
    ...currentAmenity,
    status: isActive ? 'Active' : 'Inactive',
    isActive,
  };

  return updateAmenity(amenityId, updatedAmenity);
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

// The COMPLETE write vocabulary of `POST/PUT /dashboard/amenities` — the only
// amenity write endpoints that exist. Their `AmenityWrite` model is
// `extra="forbid"`, so adding any other key (opening/closing times, a
// `settings` group) makes every save 422; and the repository behind them
// writes no hours columns on either schema generation. The Add Amenity form
// COLLECTS opening/closing times and this function is where they fall on the
// floor — knowingly, because there is nowhere to send them: the backend's
// hours-capable save (`SaveAmenityRequest.settings` →
// `amenities_service.save_amenity`) lost its routes when the catalogue
// endpoints were removed as duplicates. Until the backend accepts hours on
// this wire (backend follow-up, reported 2026-08-12), amenity hours CANNOT be
// persisted from the frontend — which is why the cards no longer display
// invented ones.
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
});
