import { expect, test } from '@playwright/test';

async function routePublicAuth(page, session = null) {
  await page.route('**/api/v1/auth/methods', (route) => route.fulfill({
    json: {
      primary: 'google',
      methods: [
        { id: 'google', kind: 'redirect', label: 'Continue with Google' },
        { id: 'email_password', kind: 'credentials', label: 'Continue with email' },
      ],
    },
  }));
  await page.route('**/api/v1/auth/session', (route) => route.fulfill(
    session ? { json: session } : { status: 401, json: {} },
  ));
  await page.route('**/api/v1/auth/refresh', (route) => route.fulfill({ status: 401, json: {} }));
  await page.route('**/api/v1/auth/csrf', (route) => route.fulfill({
    json: { message: 'CSRF protection ready.' },
    headers: { 'set-cookie': 'hb_preauth_csrf=e2e; Path=/; SameSite=Lax' },
  }));
}

test('professional CTA opens the existing auth module in create-account mode', async ({ page }) => {
  await routePublicAuth(page);
  await page.route('**/api/v1/telemetry/service-signup', (route) => route.fulfill({
    json: { message: 'Recorded.' },
  }));
  await page.goto('/');
  const link = page.getByRole('link', { name: 'Sign up here' });
  await expect(link).toHaveAttribute('href', '/register?intent=service-provider');
  await link.click();
  await expect(page).toHaveURL(/\/register\?intent=service-provider$/);
  await expect(page.getByRole('button', { name: 'Create account', exact: true }).first()).toHaveClass(/bg-indigo-600/);
  await expect(page.getByRole('button', { name: /continue with google/i })).toBeVisible();
});

test('an existing resident cannot repurpose their account through the service intent', async ({ page }) => {
  await routePublicAuth(page, {
    identity: { id: 'resident-id', email: 'resident@example.test', full_name: 'Resident' },
    membership: { id: 'membership-id', community_id: 'community-id', role: 'resident' },
    portal: 'resident',
    onboarding_eligible: false,
  });
  await page.route('**/api/v1/telemetry/service-signup', (route) => route.fulfill({ json: { message: 'Recorded.' } }));

  await page.goto('/register?intent=service-provider');
  await expect(page.getByText('Use a separate professional account')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Return to my dashboard' })).toBeVisible();
});

test('telemetry failure never blocks the professional CTA', async ({ page }) => {
  await routePublicAuth(page);
  await page.route('**/api/v1/telemetry/service-signup', (route) => route.fulfill({ status: 503, json: {} }));

  await page.goto('/');
  await page.getByRole('link', { name: 'Sign up here' }).click();
  await expect(page).toHaveURL(/\/register\?intent=service-provider$/);
  await expect(page.getByRole('button', { name: /continue with google/i })).toBeVisible();
});

test('Google OAuth carries the allowlisted service intent through the callback boundary', async ({ page }) => {
  await routePublicAuth(page);
  await page.route('**/api/v1/telemetry/service-signup', (route) => route.fulfill({ json: { message: 'Recorded.' } }));
  await page.route('**/api/v1/auth/oauth/google/start?*', (route) => route.fulfill({ status: 204 }));
  await page.goto('/register?intent=service-provider');

  const started = page.waitForRequest((request) => request.url().includes('/auth/oauth/google/start'));
  await page.getByRole('button', { name: /continue with google/i }).click();
  const request = await started;
  const next = new URL(request.url()).searchParams.get('next');
  expect(next).toBe('/auth/callback?intent=service-provider');
});
