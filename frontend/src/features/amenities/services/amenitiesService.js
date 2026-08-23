import { getDashboardSnapshot } from '../../../lib/dashboard/dashboardApi.js';
import { api } from '../../../lib/api/client.js';
import {
  createAmenitySettingsFormValues,
  mergeAmenitySettings,
  normalizeAmenityRecord,
} from '../utils/amenitySettingsModel.js';
import { MAX_IMAGE_DATA_URL_LENGTH } from '../utils/downscaleImage.js';
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

// One PUT, and the record the caller should now show — no read-back.
//
// `PUT /dashboard/amenities/{id}` answers with the saved database ROW
// (snake_case, straight out of the repository), not the snapshot projection
// the rest of this module speaks, so re-reading the snapshot used to be the
// only way to get a shaped record back. That read cost the whole admin
// snapshot — users, complaints, visitors, bookings, payments, notices — per
// save, and a status toggle paid for three of them. What we PUT is what the
// row now contains, so the merged record IS the answer; the `dashboard.refresh`
// frame the endpoint publishes brings any server-side derivation along behind
// it.
const saveAmenity = async (currentAmenity, amenityData) => {
  const isActive = amenityData.isActive ?? currentAmenity.isActive;
  const updatedAmenity = normalizeAmenityRecord({
    ...currentAmenity,
    ...amenityData,
    ...normalizeBookingConfiguration(amenityData, currentAmenity),
    id: currentAmenity.id,
    status: isActive ? 'Active' : 'Inactive',
    isActive,
  });

  await api(`/dashboard/amenities/${updatedAmenity.id}`, {
    method: 'PUT',
    body: JSON.stringify(toAmenityWrite(updatedAmenity)),
  });
  return updatedAmenity;
};

export const createAmenity = async (amenityData) => {
  const isActive = amenityData.isActive ?? true;
  const created = await api('/dashboard/amenities', {
    method: 'POST',
    body: JSON.stringify(toAmenityWrite(amenityData)),
  });

  // Built from the form's own values plus the id the endpoint assigned, for
  // the same reason as `saveAmenity`: the response is a raw row and a snapshot
  // read to reshape it is a whole-community round trip for one new card.
  return normalizeAmenityRecord({
    ...amenityData,
    ...normalizeBookingConfiguration(amenityData),
    id: created?.id ?? created?.amenityId ?? null,
    status: isActive ? 'Active' : 'Inactive',
    isActive,
  });
};

export const updateAmenity = async (amenityId, amenityData) => {
  const amenities = await readAmenities();
  const amenityIndex = findAmenityIndex(amenities, amenityId);
  return saveAmenity(amenities[amenityIndex], amenityData);
};

export const removeAmenity = async (amenityId) => {
  const amenities = await readAmenities();
  findAmenityIndex(amenities, amenityId);
  await api(`/dashboard/amenities/${amenityId}`, { method: 'DELETE' });
  return amenityId;
};

/**
 * Flip one boolean, with one round trip.
 *
 * `knownAmenity` is the record the caller is already rendering — the card
 * whose switch was just clicked. Given it, the toggle is a single PUT and no
 * snapshot read at all; without it, exactly one read finds the record to
 * flip. It used to cost three (this function, then `updateAmenity`, then the
 * `getAmenityById` read-back), which is what issue #48 D1 measures.
 */
export const setAmenityActiveStatus = async (amenityId, knownAmenity = null) => {
  const currentAmenity =
    knownAmenity && knownAmenity.id === amenityId
      ? normalizeAmenityRecord(knownAmenity)
      : await readAmenities().then(
          (amenities) => amenities[findAmenityIndex(amenities, amenityId)]
        );
  const isActive = !currentAmenity.isActive;

  return saveAmenity(currentAmenity, {
    status: isActive ? 'Active' : 'Inactive',
    isActive,
  });
};

export const updateAmenitySettings = async (amenityId, settings) => {
  const amenities = await readAmenities();
  const amenityIndex = findAmenityIndex(amenities, amenityId);
  const currentAmenity = amenities[amenityIndex];
  const updatedAmenity = mergeAmenitySettings(currentAmenity, settings);
  const validationErrors = validateAmenitySettings(
    createAmenitySettingsFormValues(updatedAmenity)
  );

  if (Object.keys(validationErrors).length > 0) {
    throw new Error(Object.values(validationErrors)[0]);
  }

  return saveAmenity(currentAmenity, updatedAmenity);
};

// `HH:MM`, or null for anything that is not a clock time. `AmenityWrite`
// accepts "HH:MM" / "HH:MM:SS" / null and 422s the rest, and the settings
// model seeds its form fields with strings that may never have been saved, so
// the shapes that reach here are wider than the ones that may leave.
const toClockWrite = (value) => {
  const text = String(value ?? '').trim();
  const match = /^(\d{1,2}):([0-5]\d)(?::[0-5]\d)?$/.exec(text);

  if (!match) {
    return null;
  }

  const hours = Number(match[1]);
  return hours > 23 ? null : `${String(hours).padStart(2, '0')}:${match[2]}`;
};

// Hours only leave when they are the RECORD's hours. `normalizeAmenityRecord`
// lays the settings-form defaults (06:00-22:00) over every hoursless amenity so
// the time inputs have something to edit; writing those back would turn a
// status toggle into a silent decision about when the clubhouse opens.
// `hasStoredHours` is that distinction, carried on the record.
const toHoursWrite = (amenity) => {
  const openingTime = toClockWrite(amenity.openingTime);
  const closingTime = toClockWrite(amenity.closingTime);
  const isRealWindow =
    amenity.hasStoredHours !== false &&
    Boolean(openingTime) &&
    Boolean(closingTime) &&
    // Mirrors the DB's `amenities_hours_check` and `AmenityWrite`'s model
    // validator; the create/settings forms refuse it first, so reaching here
    // means the record itself never held a usable window.
    openingTime < closingTime;

  return isRealWindow
    ? { opening_time: openingTime, closing_time: closingTime }
    : { opening_time: null, closing_time: null };
};

// `AmenityWrite.image` takes an `https://` URL (<= 2000 chars) or a
// `data:image/(png|jpeg|webp|gif);base64,` URL of at most
// `MAX_IMAGE_DATA_URL_LENGTH` characters — the amenity photo lives in the
// `amenities.image_url` column itself, there is no bucket. A value that fits
// neither is refused HERE, with a sentence the admin can act on, rather than
// dropped on the floor (the picture vanishes without a word — issue #48 D2) or
// posted for the backend to 422 in Pydantic's own words.
const IMAGE_DATA_URL = /^data:image\/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+$/;
const MAX_IMAGE_URL_LENGTH = 2000;

const toImageWrite = (image) => {
  const value = String(image ?? '').trim();

  if (!value) {
    return null;
  }

  if (/^https:\/\//i.test(value)) {
    if (value.length > MAX_IMAGE_URL_LENGTH) {
      throw new Error('The amenity image link is too long to save.');
    }

    return value;
  }

  if (IMAGE_DATA_URL.test(value)) {
    if (value.length > MAX_IMAGE_DATA_URL_LENGTH) {
      throw new Error(
        'The amenity image is too large to save. Choose it again so it can be resized.'
      );
    }

    return value;
  }

  throw new Error(
    'The amenity image must be an uploaded picture or an https:// link.'
  );
};

// The COMPLETE write vocabulary of `POST/PUT /dashboard/amenities` — the only
// amenity write endpoints that exist. `AmenityWrite` is `extra="forbid"`, so
// any key not on this list makes every save a 422.
//
// It now carries the three fields the Add Amenity form always collected and
// this function used to discard: the picture and the opening/closing times.
// They had nowhere to go — the hours-capable save lost its routes when the
// catalogue endpoints were removed as duplicates — so the form quietly threw
// them away on every submit. Issue #48 put them on this wire (contract §A/§B:
// `image` -> the `image_url` column, `opening_time`/`closing_time` -> the real
// hours columns that migration 0023 added), and they are sent here.
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
  image: toImageWrite(amenity.image),
  ...toHoursWrite(amenity),
});
