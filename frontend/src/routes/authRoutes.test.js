import { describe, expect, it } from 'vitest';
import {
  AUTH_ROUTES,
  SERVICE_PROVIDER_INTENT,
  authIntentFromSearch,
  destinationAfterAuth,
  serviceIntentConflictsWithMembership,
} from './authRoutes';

describe('service-provider authentication intent', () => {
  it('accepts only the allowlisted value', () => {
    expect(authIntentFromSearch('?intent=service-provider')).toBe(SERVICE_PROVIDER_INTENT);
    expect(authIntentFromSearch('?intent=admin')).toBeNull();
    expect(authIntentFromSearch('?intent=service-provider%2F..%2Fadmin')).toBeNull();
  });

  it('routes a membership-less identity to worker onboarding', () => {
    expect(destinationAfterAuth({ identity: { id: 'p1' }, membership: null }, SERVICE_PROVIDER_INTENT))
      .toBe(AUTH_ROUTES.WORKER_DASHBOARD);
  });

  it('does not let the URL override an existing resident portal', () => {
    const context = { identity: { id: 'p1' }, membership: { role: 'resident' }, portal: 'resident' };
    expect(serviceIntentConflictsWithMembership(context, SERVICE_PROVIDER_INTENT)).toBe(true);
    expect(destinationAfterAuth(context, SERVICE_PROVIDER_INTENT)).toBe(AUTH_ROUTES.RESIDENT_DASHBOARD);
  });

  it('keeps established professional portals valid', () => {
    for (const portal of ['worker', 'security']) {
      expect(serviceIntentConflictsWithMembership(
        { membership: { role: portal }, portal }, SERVICE_PROVIDER_INTENT,
      )).toBe(false);
    }
    expect(serviceIntentConflictsWithMembership(
      { membership: { role: 'manager' }, portal: 'security-manager' }, SERVICE_PROVIDER_INTENT,
    )).toBe(true);
  });
});
