const API_BASE = '/api/v1';

function csrfToken() {
  return document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('__Host-hb_csrf=') || cookie.startsWith('hb_csrf='))
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

export async function api(path, options = {}, { retry = true } = {}) {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes((options.method || 'GET').toUpperCase())) {
    headers.set('X-CSRF-Token', csrfToken());
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' });
  if (response.status === 401 && retry && path !== '/auth/refresh') {
    const refreshed = await refresh();
    if (refreshed.ok) return api(path, options, { retry: false });
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
