export const onboardingModules = Object.freeze([
  {
    id: 'resident-management',
    name: 'Resident Management',
    description: 'Manage residents and their profiles.',
    icon: 'residents',
    defaultEnabled: true,
  },
  {
    id: 'visitor-management',
    name: 'Visitor Management',
    description: 'Approve and track visitors.',
    icon: 'visitors',
    defaultEnabled: true,
  },
  {
    id: 'complaint-management',
    name: 'Complaint Management',
    description: 'Residents can raise complaints.',
    icon: 'complaints',
    defaultEnabled: true,
  },
  {
    id: 'maintenance-billing',
    name: 'Maintenance & Billing',
    description: 'Track maintenance payments and dues.',
    icon: 'billing',
    defaultEnabled: true,
  },
  {
    id: 'notice-board',
    name: 'Notice Board',
    description: 'Publish announcements.',
    icon: 'notices',
    defaultEnabled: true,
  },
  {
    id: 'amenities-booking',
    name: 'Amenities Booking',
    description: 'Book clubhouse, gym, pool, etc.',
    icon: 'amenities',
    defaultEnabled: false,
  },
  {
    id: 'security-gate-management',
    name: 'Security & Gate Management',
    description: 'Gate entry and security logs.',
    icon: 'security',
    defaultEnabled: false,
  },
  {
    id: 'parking-management',
    name: 'Parking Management',
    description: 'Manage resident and visitor parking.',
    icon: 'parking',
    defaultEnabled: false,
  },
  {
    id: 'staff-management',
    name: 'Staff Management',
    description: 'Manage housekeeping, electricians, plumbers, etc.',
    icon: 'staff',
    defaultEnabled: false,
  },
  {
    id: 'community-marketplace',
    name: 'Community Marketplace',
    description: 'Residents can buy, sell, and exchange items.',
    icon: 'marketplace',
    defaultEnabled: false,
  },
]);

export const defaultEnabledModules = Object.freeze(
  onboardingModules
    .filter((module) => module.defaultEnabled)
    .map((module) => module.id)
);
