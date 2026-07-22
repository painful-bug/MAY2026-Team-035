export const WEEK_DAYS = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];

export const CURRENCY_OPTIONS = [
  { value: 'INR', label: 'Indian Rupee (INR)' },
  { value: 'USD', label: 'US Dollar (USD)' },
];

export const MAINTENANCE_INTERVAL_OPTIONS = [
  'Weekly',
  'Monthly',
  'Quarterly',
  'As Needed',
];

export const DEFAULT_AMENITY_SETTINGS = {
  location: '',
  operatingHours: {
    openingTime: '06:00',
    closingTime: '22:00',
    slotDurationMinutes: 60,
    cleaningBufferMinutes: 0,
  },
  bookingSettings: {
    mode: 'Shared',
    maxActiveBookingsPerResident: null,
    requireAdminApproval: false,
    allowPrivateBooking: false,
    allowRecurringBooking: false,
    allowGuestBooking: true,
    allowSameDayBooking: true,
    enableWaitlist: false,
    enableAutoApproval: false,
  },
  paymentSettings: {
    bookingFee: 0,
    securityDeposit: 0,
    lateCancellationCharge: 0,
    damageDeposit: 0,
    refundPolicy: '',
    currency: 'INR',
  },
  availabilitySettings: {
    closedDays: [],
    maintenanceDays: [],
    holidayOverrides: [],
    temporaryClosure: false,
    minimumBookingDurationMinutes: 60,
    maximumBookingDurationMinutes: 180,
    advanceBookingWindowDays: 30,
  },
  maintenanceSettings: {
    interval: 'Monthly',
    defaultDurationMinutes: 60,
    autoBlockSlots: false,
    notes: '',
  },
};
