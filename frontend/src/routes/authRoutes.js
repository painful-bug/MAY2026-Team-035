export const AUTH_ROUTES = Object.freeze({
  HOME: '/',
  LOGIN: '/login',
  AUTH_CALLBACK: '/auth/callback',
  RESIDENT_LANDING: '/residentlanding',
  RESIDENT_LOGIN: '/residentlogin',
  OTP_VERIFICATION: '/admin-otp-verification',
  ASSOCIATION_REGISTRATION: '/association-registration',
  MAP_CONFIGURATION: '/map-configuration',
  FEATURE_CONFIGURATION: '/feature-configuration',
  ADMIN_PROFILE: '/admin-profile',
  ONBOARDING_OTP: '/onboarding-otp-verification',
  ONBOARDING_SUCCESS: '/onboarding-success',
  ADMIN_DASHBOARD: '/admin',
  RESIDENT_DASHBOARD: '/resident',
  SECURITY_DASHBOARD: '/security',
  SECURITY_MANAGER_DASHBOARD: '/security-manager',
});

export const getDashboardRouteForRole = (role) => {
  if (role === 'Admin') return AUTH_ROUTES.ADMIN_DASHBOARD;
  if (role === 'SecurityManager') {
    return AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD;
  }
  if (role === 'Security') return AUTH_ROUTES.SECURITY_DASHBOARD;
  return AUTH_ROUTES.RESIDENT_DASHBOARD;
};
