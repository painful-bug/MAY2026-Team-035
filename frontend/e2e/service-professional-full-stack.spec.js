import { expect, test } from '@playwright/test';

test.skip(!process.env.RUN_FULL_STACK_E2E, 'requires FastAPI and a reset local Supabase stack');

const supabaseUrl = process.env.SUPABASE_URL;
const anonKey = process.env.SUPABASE_ANON_KEY;
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

async function request(path, { method = 'GET', body, token = serviceKey } = {}) {
  const response = await fetch(`${supabaseUrl}${path}`, {
    method,
    headers: {
      apikey: token === serviceKey ? serviceKey : anonKey,
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${method} ${path}: ${response.status} ${await response.text()}`);
  return response.status === 204 ? null : response.json();
}

async function createConfirmedUser(label) {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const emailLabel = label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  const email = `${emailLabel}-${suffix}@example.test`;
  const password = `HomeBandhu-${suffix}-Password!`;
  const created = await request('/auth/v1/admin/users', {
    method: 'POST',
    body: { email, password, email_confirm: true },
  });
  const id = created.id ?? created.user?.id;
  await request('/rest/v1/profiles', {
    method: 'POST',
    body: { id, full_name: label, display_email: email },
  });
  return { id, email, password };
}

async function passwordToken(user) {
  const response = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: { apikey: anonKey, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: user.email, password: user.password }),
  });
  if (!response.ok) throw new Error(`manager sign-in failed: ${response.status}`);
  return (await response.json()).access_token;
}

test('email login, atomic profile, nearest application, approval, and next login', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'full-stack flow runs once; entry coverage runs on mobile');

  const provider = await createConfirmedUser('Full Stack Provider');
  const manager = await createConfirmedUser('Full Stack Manager');
  const [skill] = await request('/rest/v1/skills?name=eq.Plumbing&select=id');
  const [community] = await request('/rest/v1/communities', {
    method: 'POST',
    body: {
      name: `Full Stack Community ${Date.now()}`,
      community_type: 'apartment',
      address_line1: '1 Integration Road',
      city: 'Kolkata',
      state: 'West Bengal',
      postal_code: '700001',
      latitude: 22.572645,
      longitude: 88.363892,
    },
  });
  const [department] = await request('/rest/v1/departments', {
    method: 'POST',
    body: { community_id: community.id, name: 'Maintenance', kind: 'service' },
  });
  const [category] = await request('/rest/v1/complaint_categories', {
    method: 'POST',
    body: { community_id: community.id, name: 'Plumbing', skill_id: skill.id },
  });
  await request('/rest/v1/department_categories', {
    method: 'POST',
    body: { department_id: department.id, category_id: category.id },
  });
  await request('/rest/v1/community_memberships', {
    method: 'POST',
    body: {
      community_id: community.id,
      profile_id: manager.id,
      department_id: department.id,
      role: 'manager',
      status: 'active',
    },
  });

  await page.goto('/register?intent=service-provider');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByPlaceholder('Email').fill(provider.email);
  await page.getByPlaceholder('Password').fill(provider.password);
  await page.getByRole('button', { name: 'Continue with email' }).click();

  await expect(page).toHaveURL(/\/worker$/);
  await expect(page.getByRole('heading', { name: 'Register as a service partner' })).toBeVisible();
  // The LocationPicker keeps the raw coordinate inputs inside a collapsed
  // <details> fallback; open it before filling, as a keyboard user would.
  await page.getByText('Enter coordinates manually').click();
  await page.getByLabel('Latitude').fill('22.572645');
  await page.getByLabel('Longitude').fill('88.363892');
  await page.getByRole('button', { name: 'Plumbing' }).click();
  await page.getByRole('button', { name: 'Next' }).click();

  await expect(page).toHaveURL(/\/worker\/communities\?tab=find$/);
  const communityCard = page
    .getByText(community.name, { exact: true })
    .locator('xpath=ancestor::div[.//button][1]');
  await expect(communityCard).toBeVisible();
  await communityCard.getByRole('button', { name: 'Apply · Maintenance' }).click();
  await expect(page).toHaveURL(/tab=applications/);
  await expect(page.getByText('pending', { exact: true })).toBeVisible();

  const [application] = await request(
    `/rest/v1/service_applications?service_provider_id=not.is.null&department_id=eq.${department.id}&select=id&limit=1`,
  );
  const managerToken = await passwordToken(manager);
  await request('/rest/v1/rpc/decide_service_application', {
    method: 'POST',
    token: managerToken,
    body: {
      p_application_id: application.id,
      p_decision: 'accepted',
      p_rank: 'member',
      p_job_title: 'Plumber',
      p_shift: 'Day',
      p_note: null,
    },
  });

  await page.reload();
  await expect(page.getByText('accepted', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Logout' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByPlaceholder('Email').fill(provider.email);
  await page.getByPlaceholder('Password').fill(provider.password);
  await page.getByRole('button', { name: 'Continue with email' }).click();
  await expect(page).toHaveURL(/\/worker$/);
});

test('an accepted security-department hire signs in to the security portal', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'full-stack flow runs once; route helpers cover both portals');

  const provider = await createConfirmedUser('Full Stack Guard');
  const manager = await createConfirmedUser('Full Stack Security Manager');
  const [skill] = await request('/rest/v1/skills?name=eq.Security%20Guard&select=id');
  const [community] = await request('/rest/v1/communities', {
    method: 'POST',
    body: {
      name: `Full Stack Security ${Date.now()}`,
      community_type: 'apartment',
      address_line1: '2 Integration Road',
      city: 'Kolkata',
      state: 'West Bengal',
      postal_code: '700002',
      latitude: 22.572645,
      longitude: 88.363892,
    },
  });
  const [department] = await request('/rest/v1/departments', {
    method: 'POST',
    body: { community_id: community.id, name: 'Security', kind: 'security' },
  });
  const [category] = await request('/rest/v1/complaint_categories', {
    method: 'POST',
    body: { community_id: community.id, name: 'Guarding', skill_id: skill.id },
  });
  await request('/rest/v1/department_categories', {
    method: 'POST',
    body: { department_id: department.id, category_id: category.id },
  });
  await request('/rest/v1/community_memberships', {
    method: 'POST',
    body: {
      community_id: community.id,
      profile_id: manager.id,
      department_id: department.id,
      role: 'manager',
      status: 'active',
    },
  });

  const providerToken = await passwordToken(provider);
  const providerId = await request('/rest/v1/rpc/register_service_provider', {
    method: 'POST',
    token: providerToken,
    body: {
      p_display_name: 'Full Stack Guard',
      p_headline: 'Security guard',
      p_phone_e164: null,
      p_latitude: 22.572645,
      p_longitude: 88.363892,
      p_service_radius_km: 15,
      p_skill_ids: [skill.id],
    },
  });
  const applicationId = await request('/rest/v1/rpc/apply_to_department', {
    method: 'POST',
    token: providerToken,
    body: { p_department_id: department.id, p_message: null },
  });
  await request('/rest/v1/rpc/decide_service_application', {
    method: 'POST',
    token: await passwordToken(manager),
    body: {
      p_application_id: applicationId,
      p_decision: 'accepted',
      p_rank: 'member',
      p_job_title: 'Security Guard',
      p_shift: 'Day',
      p_note: null,
    },
  });
  expect(providerId).toBeTruthy();

  await page.goto('/login');
  await page.getByPlaceholder('Email').fill(provider.email);
  await page.getByPlaceholder('Password').fill(provider.password);
  await page.getByRole('button', { name: 'Continue with email' }).click();
  await expect(page).toHaveURL(/\/security$/);
});
