import { expect, test } from '@playwright/test';

const portalCases = [
  { name: 'resident', path: '/resident', role: 'resident', portal: 'resident' },
  { name: 'worker', path: '/worker', role: 'worker', portal: 'worker' },
  { name: 'manager', path: '/manager', role: 'manager', portal: 'manager' },
  { name: 'security', path: '/security', role: 'security', portal: 'security' },
  { name: 'security manager', path: '/security-manager', role: 'manager', portal: 'security-manager' },
];

const dashboardSnapshot = {
  users: [], complaints: [], visitors: [], amenities: [], bookings: [],
  payments: [], notices: [], departments: [], activities: [], pendingRequests: [],
  weeklyNew: null,
};

function sessionFor({ role, portal }) {
  return {
    identity: { id: `${portal}-user`, email: `${portal}@example.test`, full_name: portal },
    membership: {
      id: `${portal}-membership`, community_id: 'community-1', role,
      department_id: role === 'manager' ? 'department-1' : null,
      unit: { unit_code: '10A', building_name: 'Tower A' },
    },
    portal,
    onboarding_eligible: false,
  };
}

async function mockApi(page, session) {
  const requests = [];
  await page.addInitScript(() => {
    window.__eventSources = [];
    window.EventSource = class {
      constructor(url) {
        this.url = url;
        this.closed = false;
        window.__eventSources.push(this);
      }

      addEventListener() {}
      close() { this.closed = true; }
    };
  });
  await page.route('**/api/v1/**', (route) => {
    const url = new URL(route.request().url());
    requests.push(url.pathname);
    if (url.pathname === '/api/v1/auth/session') {
      return route.fulfill(session
        ? { json: session }
        : { status: 401, json: { error: { code: 'not_authenticated' } } });
    }
    if (url.pathname === '/api/v1/dashboard/snapshot') {
      return route.fulfill({ json: dashboardSnapshot });
    }
    if (url.pathname === '/api/v1/resident/snapshot') {
      return route.fulfill({ json: {} });
    }
    if (url.pathname === '/api/v1/worker/snapshot') {
      return route.fulfill({ json: { provider: null, communities: [] } });
    }
    if (url.pathname === '/api/v1/notifications') {
      return route.fulfill({ json: { items: [], unread: 0 } });
    }
    if (url.pathname === '/api/v1/messages/threads') {
      return route.fulfill({ json: [] });
    }
    if (url.pathname.startsWith('/api/v1/security/')) {
      return route.fulfill(url.pathname.endsWith('/offline-bundle')
        ? { json: { passes: [] } }
        : { json: [] });
    }
    return route.fulfill({ json: {} });
  });
  return requests;
}

test('public pages do not request protected portal data', async ({ page }) => {
  const requests = await mockApi(page, null);
  await page.goto('/');
  await expect.poll(() => requests.includes('/api/v1/auth/session')).toBe(true);

  expect(requests.filter((path) => [
    '/api/v1/dashboard/', '/api/v1/resident/', '/api/v1/worker/',
    '/api/v1/security/', '/api/v1/notifications', '/api/v1/messages/',
  ].some((prefix) => path.startsWith(prefix)))).toEqual([]);
});

for (const portal of portalCases) {
  test(`${portal.name} does not request the admin dashboard snapshot`, async ({ page }) => {
    const requests = await mockApi(page, sessionFor(portal));
    await page.goto(portal.path);
    await expect.poll(() => requests.includes('/api/v1/messages/threads')).toBe(true);

    expect(requests).not.toContain('/api/v1/dashboard/snapshot');
  });
}

test('admin keeps its snapshot and canonical stream scoped to the admin layout', async ({ page }) => {
  const admin = { name: 'admin', path: '/admin', role: 'admin', portal: 'admin' };
  const requests = await mockApi(page, sessionFor(admin));
  await page.goto(admin.path);
  await expect.poll(() => requests.includes('/api/v1/dashboard/snapshot')).toBe(true);
  await expect.poll(() => page.evaluate(
    () => window.__eventSources.filter((source) => !source.closed).length,
  )).toBe(1);

  expect(await page.evaluate(() => window.__eventSources.map((source) => source.url)))
    .toEqual(expect.arrayContaining(['/api/v1/events']));
  expect(await page.evaluate(
    () => window.__eventSources.every((source) => source.url === '/api/v1/events'),
  )).toBe(true);

  await page.goto('/');
  await expect.poll(() => page.evaluate(
    () => window.__eventSources.every((source) => source.closed),
  )).toBe(true);
});
