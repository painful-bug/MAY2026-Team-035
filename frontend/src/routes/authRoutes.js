export const AUTH_ROUTES = Object.freeze({
  HOME: '/',
  LOGIN: '/login',
  REGISTER: '/register',
  AUTH_CALLBACK: '/auth/callback',
  CONFIRM_EMAIL: '/auth/confirm-email',
  FORGOT_PASSWORD: '/auth/forgot-password',
  RESET_PASSWORD: '/auth/reset-password',
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
  WORKER_DASHBOARD: '/worker',
  ACCOUNT: '/account',
});

export const SERVICE_PROVIDER_INTENT = 'service-provider';

export const authIntentFromSearch = (search = '') => (
  new URLSearchParams(search).get('intent') === SERVICE_PROVIDER_INTENT
    ? SERVICE_PROVIDER_INTENT
    : null
);

// Which portal a person lands in, keyed on the one value that already answers
// it: `portal`, which `GET /auth/session` computes and `applicationUser` copies
// onto the user object unchanged.
//
// This replaced two exported functions that answered the same question in two
// vocabularies -- `homeRouteFor`, which read the lowercase membership role off a
// session context, and `getDashboardRouteForRole`, which read a display label
// off a user object. Every new portal had to be added to both, and one of them
// was always the one somebody forgot: `SecurityManager` existed only in the
// label vocabulary, so `/security-manager` was guarded by a role no session
// could ever hold and bounced its own users back to `/security`.
//
// `portal` is the right key because the backend already derives it from facts
// the frontend does not hold -- whether a manager's department is a security
// department, and whether a person with no membership is a registered service
// provider.
const PORTAL_ROUTES = Object.freeze({
  admin: AUTH_ROUTES.ADMIN_DASHBOARD,
  'security-manager': AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD,
  security: AUTH_ROUTES.SECURITY_DASHBOARD,
  worker: AUTH_ROUTES.WORKER_DASHBOARD,
  resident: AUTH_ROUTES.RESIDENT_DASHBOARD,
});

/**
 * Where a signed-in person belongs.
 *
 * Takes either a session context from `GET /auth/session` or the user object
 * `applicationUser` builds from one; both carry `portal`, so there is one
 * lookup rather than two mappings that can drift.
 */
export const homeRouteFor = (subject) => {
  if (!subject) return AUTH_ROUTES.ACCOUNT;
  // A session context with an identity and no membership: either somebody about
  // to register a society, or a service person whose portal the backend has
  // already named for them.
  if (subject.identity && !subject.membership && !subject.portal) {
    return subject.onboarding_eligible ? AUTH_ROUTES.GET_STARTED : AUTH_ROUTES.ACCOUNT;
  }
  return PORTAL_ROUTES[subject.portal] || AUTH_ROUTES.ACCOUNT;
};

export const destinationAfterAuth = (context, intent) => (
  intent === SERVICE_PROVIDER_INTENT && context?.identity && !context.membership
    ? AUTH_ROUTES.WORKER_DASHBOARD
    : homeRouteFor(context)
);

export const serviceIntentConflictsWithMembership = (context, intent) => (
  intent === SERVICE_PROVIDER_INTENT
  && Boolean(context?.membership)
  && !['worker', 'security'].includes(context?.portal)
);
