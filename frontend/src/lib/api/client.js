const API_BASE = '/api/v1';
const AUTH_REQUEST_TIMEOUT_MS = 8_000;

function csrfToken() {
  return document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('hb_preauth_csrf=') || cookie.startsWith('hb_recovery_csrf=') || cookie.startsWith('__Host-hb_csrf=') || cookie.startsWith('hb_csrf='))
    ?.split('=')[1] ?? '';
}

let refreshPromise;

export class ApiError extends Error {
  constructor({ status, code, message, details = null }) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function refresh() {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken() },
    }).finally(() => { refreshPromise = undefined; });
  }
  return refreshPromise;
}

async function fetchWithTimeout(url, options, timeoutMs) {
  if (!timeoutMs) return fetch(url, options);

  const controller = new AbortController();
  const onAbort = () => controller.abort();
  options.signal?.addEventListener('abort', onAbort, { once: true });
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted && !options.signal?.aborted) {
      throw new ApiError({
        status: 504,
        code: 'request_timeout',
        message: 'The server did not respond in time. Please try again.',
      });
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
    options.signal?.removeEventListener('abort', onAbort);
  }
}

export async function api(path, options = {}, { retry = true, timeoutMs } = {}) {
  const method = (options.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && !csrfToken()) {
    await prepareAnonymousCsrf();
  }
  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    headers.set('X-CSRF-Token', csrfToken());
  }
  const response = await fetchWithTimeout(`${API_BASE}${path}`, {
    ...options, headers, credentials: 'include',
  }, timeoutMs);
  if (response.status === 401 && retry && path !== '/auth/refresh') {
    const refreshed = await refresh();
    if (refreshed.ok) return api(path, options, { retry: false, timeoutMs });
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = payload?.error;
    throw new ApiError({
      status: response.status,
      code: error?.code || 'request_failed',
      message: error?.message || payload?.message || (typeof payload?.detail === 'string' ? payload.detail : null) || 'Request failed.',
      details: error?.details || null,
    });
  }
  return payload;
}

export async function prepareAnonymousCsrf() {
  if (csrfToken()) return;
  await api('/auth/csrf', {}, { retry: false, timeoutMs: AUTH_REQUEST_TIMEOUT_MS });
}

export const API_TIMEOUTS = Object.freeze({
  authMethods: AUTH_REQUEST_TIMEOUT_MS,
  logout: AUTH_REQUEST_TIMEOUT_MS,
});
