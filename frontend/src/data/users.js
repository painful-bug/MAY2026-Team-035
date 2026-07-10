// apartmentId groups every phone/person that belongs to one flat. It equals the
// flat code for seed data; the admin invite flow sets it explicitly.
export const initialUsers = [
  {
    id: 'u1',
    name: 'Aakash S.',
    email: 'resident@homebandhu.com',
    role: 'Resident',
    phone: '+91 98765 43210',
    tower: 'B',
    flat: 'B-1204',
    apartmentId: 'B-1204',
    status: 'Active'
  },
  {
    id: 'u2',
    name: 'Aakash Deka',
    email: 'admin@homebandhu.com',
    role: 'Admin',
    phone: '+91 99999 88888',
    tower: 'A',
    flat: 'A-502',
    apartmentId: 'A-502',
    status: 'Active'
  },
  {
    id: 'u3',
    name: 'Rohan Sharma',
    email: 'rohan.sharma@gmail.com',
    role: 'Resident',
    phone: '+91 98123 45678',
    tower: 'C',
    flat: 'C-301',
    apartmentId: 'C-301',
    status: 'Active'
  },
  {
    id: 'u4',
    name: 'Priya Patel',
    email: 'priya.patel@outlook.com',
    role: 'Resident',
    phone: '+91 97234 56789',
    tower: 'D',
    flat: 'D-804',
    apartmentId: 'D-804',
    status: 'Active'
  },
  {
    id: 'u5',
    name: 'Vikram Singh',
    email: 'vikram.singh@yahoo.com',
    role: 'Resident',
    phone: '+91 96345 67890',
    tower: 'A',
    flat: 'A-1003',
    apartmentId: 'A-1003',
    status: 'Active'
  },
  {
    id: 'u6',
    name: 'Ravi Kumar',
    email: '',
    role: 'Resident',
    phone: '+91 98765 11111',
    tower: 'B',
    flat: '12 Cedar Lane, Block B',
    apartmentId: '12 Cedar Lane, Block B',
    residenceKey: '12 cedar lane, block b',
    status: 'Active'
  },
  {
    id: 'u7',
    name: 'Priya Kumar',
    email: '',
    role: 'Resident',
    phone: '+91 98765 22222',
    tower: 'B',
    flat: '12 Cedar Lane, Block B',
    apartmentId: '12 Cedar Lane, Block B',
    residenceKey: '12 cedar lane, block b',
    status: 'Active'
  }
];
