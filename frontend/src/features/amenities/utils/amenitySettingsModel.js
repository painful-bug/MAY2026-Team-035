import { DEFAULT_AMENITY_SETTINGS } from '../constants/amenitySettings.js';

const numberOrFallback = (value, fallback) => {
  const number = Number(value);
  return value === '' || value == null || !Number.isFinite(number)
    ? fallback
    : number;
};

const nullableNumber = (value) => {
  if (value === '' || value == null) {
    return null;
  }

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

export const formatAmenityOperatingHours = (openingTime, closingTime) => {
  const formatTime = (timeValue) => {
    if (!timeValue) {
      return '';
    }

    const [hours, minutes] = timeValue.split(':').map(Number);
    const period = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    return `${displayHours}:${String(minutes).padStart(2, '0')} ${period}`;
  };

  return openingTime && closingTime
    ? `${formatTime(openingTime)} - ${formatTime(closingTime)}`
    : '';
};

export const normalizeAmenityRecord = (amenity) => {
  const operatingHours = {
    ...DEFAULT_AMENITY_SETTINGS.operatingHours,
    ...amenity.operatingHours,
    openingTime:
      amenity.operatingHours?.openingTime ??
      amenity.openingTime ??
      DEFAULT_AMENITY_SETTINGS.operatingHours.openingTime,
    closingTime:
      amenity.operatingHours?.closingTime ??
      amenity.closingTime ??
      DEFAULT_AMENITY_SETTINGS.operatingHours.closingTime,
    slotDurationMinutes: numberOrFallback(
      amenity.operatingHours?.slotDurationMinutes ??
        amenity.bookingSlotDuration,
      DEFAULT_AMENITY_SETTINGS.operatingHours.slotDurationMinutes
    ),
    cleaningBufferMinutes: numberOrFallback(
      amenity.operatingHours?.cleaningBufferMinutes ?? amenity.cleaningBuffer,
      DEFAULT_AMENITY_SETTINGS.operatingHours.cleaningBufferMinutes
    ),
  };
  const bookingSettings = {
    ...DEFAULT_AMENITY_SETTINGS.bookingSettings,
    ...amenity.bookingSettings,
    mode:
      amenity.bookingSettings?.mode ??
      amenity.bookingMode ??
      DEFAULT_AMENITY_SETTINGS.bookingSettings.mode,
    maxActiveBookingsPerResident:
      amenity.bookingSettings?.maxActiveBookingsPerResident ??
      amenity.maxBookingsPerResident ??
      null,
    requireAdminApproval:
      amenity.bookingSettings?.requireAdminApproval ??
      amenity.requireApproval ??
      false,
    allowPrivateBooking:
      amenity.bookingSettings?.allowPrivateBooking ??
      amenity.allowPrivateBooking ??
      false,
  };
  const paymentSettings = {
    ...DEFAULT_AMENITY_SETTINGS.paymentSettings,
    ...amenity.paymentSettings,
  };
  const availabilitySettings = {
    ...DEFAULT_AMENITY_SETTINGS.availabilitySettings,
    ...amenity.availabilitySettings,
    closedDays: [...(amenity.availabilitySettings?.closedDays ?? [])],
    maintenanceDays: [
      ...(amenity.availabilitySettings?.maintenanceDays ?? []),
    ],
    holidayOverrides: [
      ...(amenity.availabilitySettings?.holidayOverrides ?? []),
    ],
  };
  const maintenanceSettings = {
    ...DEFAULT_AMENITY_SETTINGS.maintenanceSettings,
    ...amenity.maintenanceSettings,
  };

  return {
    ...amenity,
    location: amenity.location ?? DEFAULT_AMENITY_SETTINGS.location,
    capacity: nullableNumber(amenity.capacity),
    // The snapshot's amenity rows carry neither of these; the cards render
    // them raw, so an absent value must read as 0, never NaN or blank.
    pendingRequests: numberOrFallback(amenity.pendingRequests, 0),
    outstandingDues: numberOrFallback(amenity.outstandingDues, 0),
    operatingHours,
    bookingSettings,
    paymentSettings,
    availabilitySettings,
    maintenanceSettings,
    openingTime: operatingHours.openingTime,
    closingTime: operatingHours.closingTime,
    openingHours: formatAmenityOperatingHours(
      operatingHours.openingTime,
      operatingHours.closingTime
    ),
    bookingSlotDuration: operatingHours.slotDurationMinutes,
    cleaningBuffer: operatingHours.cleaningBufferMinutes,
    bookingMode: bookingSettings.mode,
    maxBookingsPerResident: bookingSettings.maxActiveBookingsPerResident,
    requireApproval: bookingSettings.requireAdminApproval,
    allowPrivateBooking: bookingSettings.allowPrivateBooking,
  };
};

export const mergeAmenitySettings = (amenity, settings) =>
  normalizeAmenityRecord({
    ...amenity,
    name: settings.name.trim(),
    description: settings.description.trim(),
    category: settings.category,
    location: settings.location.trim(),
    capacity: Number(settings.capacity),
    operatingHours: { ...settings.operatingHours },
    bookingSettings: { ...settings.bookingSettings },
    paymentSettings: { ...settings.paymentSettings },
    availabilitySettings: {
      ...settings.availabilitySettings,
      closedDays: [...settings.availabilitySettings.closedDays],
      maintenanceDays: [...settings.availabilitySettings.maintenanceDays],
      holidayOverrides: [...settings.availabilitySettings.holidayOverrides],
    },
    maintenanceSettings: { ...settings.maintenanceSettings },
    updatedAt: new Date().toISOString(),
  });

export const createAmenitySettingsFormValues = (amenity) => {
  const normalized = normalizeAmenityRecord(amenity);

  return {
    name: normalized.name,
    description: normalized.description,
    category: normalized.category,
    location: normalized.location,
    capacity: normalized.capacity == null ? '' : String(normalized.capacity),
    bookingMode: normalized.bookingSettings.mode,
    openingTime: normalized.operatingHours.openingTime,
    closingTime: normalized.operatingHours.closingTime,
    slotDurationMinutes: String(normalized.operatingHours.slotDurationMinutes),
    cleaningBufferMinutes: String(
      normalized.operatingHours.cleaningBufferMinutes
    ),
    maxActiveBookingsPerResident:
      normalized.bookingSettings.maxActiveBookingsPerResident == null
        ? ''
        : String(normalized.bookingSettings.maxActiveBookingsPerResident),
    requireAdminApproval: normalized.bookingSettings.requireAdminApproval,
    allowPrivateBooking: normalized.bookingSettings.allowPrivateBooking,
    allowRecurringBooking: normalized.bookingSettings.allowRecurringBooking,
    allowGuestBooking: normalized.bookingSettings.allowGuestBooking,
    allowSameDayBooking: normalized.bookingSettings.allowSameDayBooking,
    enableWaitlist: normalized.bookingSettings.enableWaitlist,
    enableAutoApproval: normalized.bookingSettings.enableAutoApproval,
    bookingFee: String(normalized.paymentSettings.bookingFee),
    securityDeposit: String(normalized.paymentSettings.securityDeposit),
    lateCancellationCharge: String(
      normalized.paymentSettings.lateCancellationCharge
    ),
    damageDeposit: String(normalized.paymentSettings.damageDeposit),
    refundPolicy: normalized.paymentSettings.refundPolicy,
    currency: normalized.paymentSettings.currency,
    closedDays: [...normalized.availabilitySettings.closedDays],
    maintenanceDays: [...normalized.availabilitySettings.maintenanceDays],
    holidayOverrides: normalized.availabilitySettings.holidayOverrides.join(
      '\n'
    ),
    temporaryClosure: normalized.availabilitySettings.temporaryClosure,
    minimumBookingDurationMinutes: String(
      normalized.availabilitySettings.minimumBookingDurationMinutes
    ),
    maximumBookingDurationMinutes: String(
      normalized.availabilitySettings.maximumBookingDurationMinutes
    ),
    advanceBookingWindowDays: String(
      normalized.availabilitySettings.advanceBookingWindowDays
    ),
    maintenanceInterval: normalized.maintenanceSettings.interval,
    defaultMaintenanceDurationMinutes: String(
      normalized.maintenanceSettings.defaultDurationMinutes
    ),
    autoBlockMaintenanceSlots: normalized.maintenanceSettings.autoBlockSlots,
    maintenanceNotes: normalized.maintenanceSettings.notes,
  };
};

const parseHolidayOverrides = (value) =>
  value
    .split(/[\n,]/)
    .map((date) => date.trim())
    .filter(Boolean);

export const serializeAmenitySettings = (values) => ({
  name: values.name,
  description: values.description,
  category: values.category,
  location: values.location,
  capacity: Number(values.capacity),
  operatingHours: {
    openingTime: values.openingTime,
    closingTime: values.closingTime,
    slotDurationMinutes: Number(values.slotDurationMinutes),
    cleaningBufferMinutes: Number(values.cleaningBufferMinutes),
  },
  bookingSettings: {
    mode: values.bookingMode,
    maxActiveBookingsPerResident:
      values.maxActiveBookingsPerResident === ''
        ? null
        : Number(values.maxActiveBookingsPerResident),
    requireAdminApproval: values.requireAdminApproval,
    allowPrivateBooking: values.allowPrivateBooking,
    allowRecurringBooking: values.allowRecurringBooking,
    allowGuestBooking: values.allowGuestBooking,
    allowSameDayBooking: values.allowSameDayBooking,
    enableWaitlist: values.enableWaitlist,
    enableAutoApproval: values.enableAutoApproval,
  },
  paymentSettings: {
    bookingFee: Number(values.bookingFee),
    securityDeposit: Number(values.securityDeposit),
    lateCancellationCharge: Number(values.lateCancellationCharge),
    damageDeposit: Number(values.damageDeposit),
    refundPolicy: values.refundPolicy.trim(),
    currency: values.currency,
  },
  availabilitySettings: {
    closedDays: [...values.closedDays],
    maintenanceDays: [...values.maintenanceDays],
    holidayOverrides: parseHolidayOverrides(values.holidayOverrides),
    temporaryClosure: values.temporaryClosure,
    minimumBookingDurationMinutes: Number(
      values.minimumBookingDurationMinutes
    ),
    maximumBookingDurationMinutes: Number(
      values.maximumBookingDurationMinutes
    ),
    advanceBookingWindowDays: Number(values.advanceBookingWindowDays),
  },
  maintenanceSettings: {
    interval: values.maintenanceInterval,
    defaultDurationMinutes: Number(
      values.defaultMaintenanceDurationMinutes
    ),
    autoBlockSlots: values.autoBlockMaintenanceSlots,
    notes: values.maintenanceNotes.trim(),
  },
});
