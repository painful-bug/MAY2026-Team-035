export const BOOKING_MODE = {
  SHARED: 'Shared',
  EXCLUSIVE: 'Exclusive',
  HYBRID: 'Hybrid',
};

export const BOOKING_MODE_OPTIONS = [
  {
    value: BOOKING_MODE.SHARED,
    description:
      'Multiple residents can book the same time slot until capacity is reached.',
  },
  {
    value: BOOKING_MODE.EXCLUSIVE,
    description: 'Only one booking is allowed for a time slot.',
  },
  {
    value: BOOKING_MODE.HYBRID,
    description:
      'Shared booking is allowed, but admins may reserve the entire facility as a private booking.',
  },
];
