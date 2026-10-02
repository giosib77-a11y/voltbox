/**
 * Shared fetch client for every REST call the app makes.
 *
 * What it does: builds URLs, attaches the bearer token, turns the API's error
 * envelope into the project's error classes, and retries once after a token
 * refresh on 401.
 * Where it fits: httpApi.js (storefront) and admin/adminApi.js both sit on top
 * of it, so the refresh logic exists once and benefits both.
 * Notes: kept separate from httpApi.js so a mock-mode build can pull in the
 * admin API without also pulling in the storefront's http implementation.
 */

import {
  ApiError,
  AuthError,
  ConflictError,
  NotFoundError,
  SessionExpiredError,
  ValidationError,
} from './errors.js';
import { getAccessToken, isAuthPath, readSession, refreshSession } from './session.js';
import { i18n, t } from '../i18n/index.js';

const BASE_URL = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');

/**
 * How long to wait before giving up on a request, in milliseconds.
 *
 * Long, deliberately. A free-tier host puts the API to sleep after idling and
 * the first request afterwards waits for the process to start, so a tight
 * deadline would turn a slow first page into a failed one.
 */
const REQUEST_TIMEOUT_MS = 45_000;

/** An abort signal that fires after the deadline, where the browser has one. */
function timeoutSignal() {
  // Guarded: AbortSignal.timeout is recent enough that an older browser, or a
  // test environment, may not have it. Without it the request simply behaves
  // as it did before rather than throwing here.
  return typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
    ? AbortSignal.timeout(REQUEST_TIMEOUT_MS)
    : undefined;
}

/** ავტორიზაციის ტოკენი — რეალურ backend-ზე httpOnly cookie სჯობს. */
function authHeader() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * The shopper's words for the error codes whose server message is not
 * user-facing - `apiErrors.<CODE>` in the translation files.
 *
 * `code` is the stable part of the contract and `message` is written for a
 * developer reading a log. The few codes a shopper can actually trigger get a
 * sentence that says what happened and what to do about it, in the page's
 * language. The admin panel's codes are there too; the panel is always
 * Georgian (i18n/index.js), so it reads them in Georgian.
 *
 * Two used to arrive in English — "Invalid email or password" on every
 * mistyped login, "Not enough stock" when someone else took the last one
 * first; and a 500 as "Internal server error", the server's own words for a
 * log. Each of those now has an entry.
 *
 * A few codes carry something worth saying - how many are actually left, for
 * one - so those are a function of the details rather than one sentence.
 */
const DETAILED_MESSAGES = {
  TOO_MANY_LOGIN_ATTEMPTS: (details) => {
    const seconds = Number(details?.retryAfterSeconds);
    if (!Number.isFinite(seconds) || seconds <= 0) return t('apiErrors.TOO_MANY_LOGIN_ATTEMPTS.later');
    return t('apiErrors.TOO_MANY_LOGIN_ATTEMPTS.inMinutes', { count: Math.ceil(seconds / 60) });
  },
  INSUFFICIENT_STOCK: (details) => {
    const available = Number(details?.available);
    if (Number.isFinite(available) && available > 0) {
      return t('apiErrors.INSUFFICIENT_STOCK.left', { count: available });
    }
    return t('apiErrors.INSUFFICIENT_STOCK.none');
  },
  // An iPhone saves photos as HEIC, and copied to a computer that is how they
  // arrive. It used to be "not an image", which gave no hint that the format is
  // what to change.
  UNSUPPORTED_IMAGE_FORMAT: (details) =>
    details?.detected === 'HEIC'
      ? t('apiErrors.UNSUPPORTED_IMAGE_FORMAT.heic')
      : t('apiErrors.UNSUPPORTED_IMAGE_FORMAT.other'),
  // The two an admin meets with a photo their phone has just taken. Both used
  // to say only that something was wrong with it, which reads like the upload
  // is broken rather than like something to fix in three seconds.
  IMAGE_TOO_LARGE: (details) => {
    const bytes = Number(details?.maxBytes);
    if (!Number.isFinite(bytes) || bytes <= 0) return t('apiErrors.IMAGE_TOO_LARGE.generic');
    return t('apiErrors.IMAGE_TOO_LARGE.limit', { limit: Math.round(bytes / (1024 * 1024)) });
  },
  IMAGE_TOO_MANY_PIXELS: (details) => {
    const width = Number(details?.maxWidth);
    const height = Number(details?.maxHeight);
    // The size that would pass, in this photo's own proportions. Saying only
    // "too many pixels" leaves the admin guessing how much to cut.
    if (Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0) {
      return t('apiErrors.IMAGE_TOO_MANY_PIXELS.sized', { width, height });
    }
    return t('apiErrors.IMAGE_TOO_MANY_PIXELS.generic');
  },
};

/** The words for a code, or null when the code has none of its own. */
function codeMessage(code, details) {
  if (!code) return null;
  if (DETAILED_MESSAGES[code]) return DETAILED_MESSAGES[code](details);
  const key = `apiErrors.${code}`;
  return i18n.exists(key) ? t(key) : null;
}

/**
 * Pulls message / code / details out of the backend's error envelope.
 *
 * The API always answers `{"error": {code, message, details}}`. The flat shape
 * is tolerated too so the client keeps working if an error ever comes from a
 * proxy or a middleware that does not use the envelope.
 */
function parseError(payload) {
  const envelope = payload?.error ?? payload ?? null;
  const code = envelope?.code || null;
  const details = envelope?.details ?? null;

  return {
    message: codeMessage(code, details) || envelope?.message || t('apiErrors.fallback'),
    code,
    details,
  };
}

/** query ობიექტი → search string (მასივები მძიმით). */
function toQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) {
      if (value.length) search.set(key, value.join(','));
    } else if (typeof value === 'object') {
      // filters: { brand: ['Apple'], 'specs.ram': ['8 GB'] } → brand=Apple&specs.ram=8 GB
      Object.entries(value).forEach(([k, v]) => {
        if (v === undefined || v === null) return;
        search.set(k, Array.isArray(v) ? v.join(',') : String(v));
      });
    } else {
      search.set(key, String(value));
    }
  });
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

/**
 * ერთიანი fetch wrapper — შეცდომებს იმავე კლასებად აქცევს, რასაც mock.
 *
 * 401-ზე ერთხელ ცდილობს access-ტოკენის განახლებას და მოთხოვნას იმეორებს.
 * `retried` შიდა დროშაა: მეორე 401 უკვე ნამდვილად უფლების პრობლემაა და არა
 * ვადაგასული ტოკენი — თორემ განახლება-გამეორების უსასრულო ციკლი დაიწყებოდა.
 */
export async function request(path, options = {}) {
  const { method = 'GET', body, params, signal, headers: extraHeaders, retried = false } = options;
  const url = `${BASE_URL}${path}${toQuery(params)}`;

  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

  let response;
  try {
    response = await fetch(url, {
      method,
      // A caller's own signal wins. Otherwise a default deadline, because
      // `fetch` has none: a server that accepts the connection and then never
      // answers leaves the spinner turning for as long as the tab is open, with
      // nothing to retry and nothing to read. Generous on purpose — the API
      // sleeps when idle on the current host and the first request after that
      // pays for the wake-up.
      signal: signal ?? timeoutSignal(),
      headers: {
        // FormData-ს boundary-ს ბრაუზერი თვითონ აყენებს — ხელით მითითება ტეხს
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        Accept: 'application/json',
        ...authHeader(),
        ...(extraHeaders || {}),
      },
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    });
  } catch (cause) {
    // A deadline that ran out and a connection that never opened are different
    // things to the reader: one is worth retrying now, the other means check
    // the connection.
    const message =
      cause?.name === 'TimeoutError'
        ? t('apiErrors.timeout')
        : t('apiErrors.network');
    throw new ApiError(message, 0, cause);
  }

  // ვადაგასული ტოკენი: ერთი განახლება ყველა პარალელური მოთხოვნისთვის საერთოა
  // (`refreshSession` single-flight-ია), მერე თითოეული ზუსტად ერთხელ მეორდება.
  if (response.status === 401 && !retried && !isAuthPath(path)) {
    const hadSession = Boolean(readSession());
    const token = await refreshSession();
    if (token) return request(path, { ...options, retried: true });
    // The session is gone and `refreshSession` has already redirected. One
    // recognisable type for every request caught in the same moment, so the UI
    // shows one message rather than one per pending call. A guest falls
    // through instead: their 401 is about permission, not an expired session.
    if (hadSession) throw new SessionExpiredError();
  }

  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (response.ok) return payload;

  const { message, code, details } = parseError(payload);
  if (response.status === 404) throw new NotFoundError(message);
  if (response.status === 409) throw new ConflictError(message, { code, details });
  if (response.status === 401 || response.status === 403) {
    throw new AuthError(message, response.status, { code, details });
  }
  if (response.status === 422 || response.status === 400) {
    throw new ValidationError(message, { code, details }, response.status);
  }
  throw new ApiError(message, response.status, { code, details });
}

