export const ADMIN_BOOKING_TYPES = [
  { value: 'resident', label: 'Resident Booking' },
  { value: 'private-event', label: 'Private Event' },
  { value: 'society-event', label: 'Society Event' },
  { value: 'maintenance-reservation', label: 'Maintenance Reservation' },
];

export const MAINTENANCE_DEPARTMENTS = [
  'Cleaning',
  'Electrical',
  'Plumbing',
  'Security',
  'Gardening',
];

export const BOOKING_CANCELLATION_REASONS = [
  { value: 'resident-requested', label: 'Resident Requested' },
  { value: 'duplicate-booking', label: 'Duplicate Booking' },
  { value: 'maintenance-required', label: 'Maintenance Required' },
  { value: 'policy-violation', label: 'Policy Violation' },
  { value: 'other', label: 'Other' },
];

export const BOOKING_REJECTION_REASONS = [
  { value: 'outstanding-dues', label: 'Outstanding Dues' },
  { value: 'duplicate-booking', label: 'Duplicate Booking' },
  { value: 'maintenance-scheduled', label: 'Maintenance Scheduled' },
  { value: 'policy-violation', label: 'Policy Violation' },
  {
    value: 'resident-requested-cancellation',
    label: 'Resident Requested Cancellation',
  },
  { value: 'capacity-limit-reached', label: 'Capacity Limit Reached' },
  { value: 'other', label: 'Other' },
];

export const getBookingTypeLabel = (bookingType) =>
  ADMIN_BOOKING_TYPES.find((option) => option.value === bookingType)?.label ??
  'Resident Booking';
