export const AUTH_ROUTES = Object.freeze({
  HOME: '/',
  LOGIN: '/login',
  REGISTER: '/register',
  AUTH_CALLBACK: '/auth/callback',
  GET_STARTED: '/get-started',
  RESIDENT_LANDING: '/residentlanding',
  ASSOCIATION_REGISTRATION: '/association-registration',
  MAP_CONFIGURATION: '/map-configuration',
  FEATURE_CONFIGURATION: '/feature-configuration',
  ADMIN_PROFILE: '/admin-profile',
  ONBOARDING_REVIEW: '/onboarding-review',
  ONBOARDING_SUCCESS: '/onboarding-success',
  ADMIN_DASHBOARD: '/admin',
  RESIDENT_DASHBOARD: '/resident',
  SECURITY_DASHBOARD: '/security',
  SECURITY_MANAGER_DASHBOARD: '/security-manager',
  ACCOUNT: '/account',
});

export const getDashboardRouteForRole = (role) => {
  if (role === 'Admin') return AUTH_ROUTES.ADMIN_DASHBOARD;
  if (role === 'SecurityManager') {
    return AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD;
  }
  if (role === 'Security') return AUTH_ROUTES.SECURITY_DASHBOARD;
  if (role === 'Resident' || role === 'Admin') return AUTH_ROUTES.RESIDENT_DASHBOARD;
  return AUTH_ROUTES.ACCOUNT;
};
