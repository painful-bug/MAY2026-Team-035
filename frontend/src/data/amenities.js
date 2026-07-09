export const initialAmenities = [
  {
    id: 'a1',
    name: 'Clubhouse Gym',
    description: 'Fully equipped gymnasium with treadmills, weights, and trainers.',
    timing: '06:00 AM - 10:00 PM',
    capacity: 20,
    status: 'Available'
  },
  {
    id: 'a2',
    name: 'Swimming Pool',
    description: 'Half-Olympic size outdoor swimming pool with separate kids section.',
    timing: '06:00 AM - 09:00 PM',
    capacity: 15,
    status: 'Available'
  },
  {
    id: 'a3',
    name: 'Tennis Court',
    description: 'Synthetic surface floodlit tennis court. Equipment available at reception.',
    timing: '07:00 AM - 09:00 PM',
    capacity: 4,
    status: 'Available'
  },
  {
    id: 'a4',
    name: 'Party Banquet Hall',
    description: 'Air-conditioned hall for private parties and celebrations.',
    timing: '10:00 AM - 11:00 PM',
    capacity: 150,
    status: 'Bookable'
  }
];

export const initialBookings = [
  {
    id: 'b1',
    amenityId: 'a1',
    amenityName: 'Clubhouse Gym',
    bookedBy: 'Aakash S.',
    userId: 'u1',
    flat: 'B-1204',
    date: '2026-07-09',
    timeSlot: '07:00 AM - 08:30 AM',
    status: 'Confirmed'
  },
  {
    id: 'b2',
    amenityId: 'a3',
    amenityName: 'Tennis Court',
    bookedBy: 'Aakash S.',
    userId: 'u1',
    flat: 'B-1204',
    date: '2026-07-10',
    timeSlot: '06:00 PM - 07:00 PM',
    status: 'Confirmed'
  }
];
