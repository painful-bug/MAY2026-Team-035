const AMENITY_BOOKINGS_STORAGE_KEY = 'homebandhu-amenity-bookings';
const AMENITY_BOOKINGS_SEED_VERSION_KEY =
  'homebandhu-amenity-bookings-seed-version';
const AMENITY_BOOKINGS_SEED_VERSION = '2';

let memoryFallback = null;

const normalizeBookingStatus = (booking) => {
  if (booking.status === 'active' && booking.state === 'blocked') {
    return 'blocked';
  }

  if (!booking.status) {
    return booking.state === 'blocked' ? 'blocked' : 'confirmed';
  }

  return booking.status;
};

const cloneBookings = (bookings) =>
  bookings.map((booking) => ({
    ...booking,
    status: normalizeBookingStatus(booking),
    guests: Array.isArray(booking.guests)
      ? booking.guests.map((guest) => ({ ...guest }))
      : booking.guests,
  }));

const isCurrentBookingCollection = (bookings) =>
  Array.isArray(bookings) &&
  bookings.every(
    (booking) =>
      booking &&
      typeof booking.id === 'string' &&
      typeof booking.state === 'string'
  );

const getLocalStorage = () => {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.localStorage;
};

const persistBookings = (bookings) => {
  const records = cloneBookings(bookings);
  const storage = getLocalStorage();

  if (storage) {
    storage.setItem(AMENITY_BOOKINGS_STORAGE_KEY, JSON.stringify(records));
    storage.setItem(
      AMENITY_BOOKINGS_SEED_VERSION_KEY,
      AMENITY_BOOKINGS_SEED_VERSION
    );
  } else {
    memoryFallback = records;
  }

  return cloneBookings(records);
};

export const loadAmenityBookings = (initialBookings) => {
  const storage = getLocalStorage();

  if (!storage) {
    if (memoryFallback === null) {
      memoryFallback = cloneBookings(initialBookings);
    }

    return cloneBookings(memoryFallback);
  }

  const persistedValue = storage.getItem(AMENITY_BOOKINGS_STORAGE_KEY);

  if (persistedValue === null) {
    return persistBookings(initialBookings);
  }

  try {
    let bookings = JSON.parse(persistedValue);

    if (!isCurrentBookingCollection(bookings)) {
      throw new TypeError('Persisted amenity bookings are invalid.');
    }

    if (
      storage.getItem(AMENITY_BOOKINGS_SEED_VERSION_KEY) !==
      AMENITY_BOOKINGS_SEED_VERSION
    ) {
      const existingIds = new Set(bookings.map((booking) => booking.id));
      const newApprovalSeeds = initialBookings.filter(
        (booking) => booking.requiresApproval && !existingIds.has(booking.id)
      );
      bookings = [...bookings, ...newApprovalSeeds];
      return persistBookings(bookings);
    }

    return cloneBookings(bookings);
  } catch {
    return persistBookings(initialBookings);
  }
};

export const saveAmenityBookings = (bookings) =>
  persistBookings(bookings);
