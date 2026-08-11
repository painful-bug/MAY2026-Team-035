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

// A file, not a payload — `api()` above always parses JSON, and
// `GET /security/exports/{dataset}` answers `text/csv`. Rather than teach
// `api()` a second content type, this is its sibling: same cookie session, same
// `ApiError` on failure (the error body IS json, even here), and the browser's
// own download path for the success case.
//
// No 401-refresh retry, unlike `api()`. A download is always a button a person
// just pressed, so a stale session surfaces as the inline error that button
// already renders, and a silent refresh would only move the same failure later.
export async function download(path, { filename } = {}) {
  const response = await fetch(`${API_BASE}${path}`, { credentials: 'include' });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = payload?.error;
    throw new ApiError({
      status: response.status,
      code: error?.code || 'request_failed',
      message: error?.message || 'Could not download that file.',
      details: error?.details || null,
    });
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename || filenameFrom(response) || 'download.csv';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/** The server names the file in `Content-Disposition`; honour it when it does. */
export function filenameFrom(response) {
  const header = response.headers?.get?.('Content-Disposition') || '';
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  return match ? decodeURIComponent(match[1].trim()) : '';
}

export async function prepareAnonymousCsrf() {
  if (csrfToken()) return;
  await api('/auth/csrf', {}, { retry: false, timeoutMs: AUTH_REQUEST_TIMEOUT_MS });
}

export const API_TIMEOUTS = Object.freeze({
  authMethods: AUTH_REQUEST_TIMEOUT_MS,
  logout: AUTH_REQUEST_TIMEOUT_MS,
});
