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

import { ApiError, AuthError, ConflictError, NotFoundError, ValidationError } from './errors.js';
import { getAccessToken, isAuthPath, refreshSession } from './session.js';

const BASE_URL = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');

/** ავტორიზაციის ტოკენი — რეალურ backend-ზე httpOnly cookie სჯობს. */
function authHeader() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Georgian text for the error codes whose server message is not user-facing.
 *
 * `code` is the stable part of the contract and `message` is written for a
 * developer reading a log. Everything the UI is in is Georgian, so the few
 * codes a shopper can actually trigger get a sentence that says what happened
 * and what to do about it.
 */
const CODE_MESSAGES = {
  RATE_LIMITED: 'ძალიან ბევრი მცდელობა იყო. დაელოდეთ ერთ წუთს და სცადეთ ხელახლა.',
  ADMIN_REQUIRED: 'ამ გვერდზე წვდომა მხოლოდ ადმინისტრატორს აქვს.',
  ACCOUNT_DISABLED: 'ანგარიში დაბლოკილია. დაუკავშირდით მაღაზიას.',
  INVALID_TOKEN: 'სესიის ვადა ამოიწურა. გთხოვთ, ხელახლა შეხვიდეთ.',
  EMAIL_ALREADY_EXISTS: 'ამ ელ. ფოსტით მომხმარებელი უკვე რეგისტრირებულია.',
};

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
  return {
    message:
      CODE_MESSAGES[code] || envelope?.message || 'მოთხოვნის დამუშავება ვერ მოხერხდა',
    code,
    details: envelope?.details ?? null,
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
      signal,
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
    throw new ApiError('სერვერთან კავშირი ვერ დამყარდა', 0, cause);
  }

  // ვადაგასული ტოკენი: ერთი განახლება ყველა პარალელური მოთხოვნისთვის საერთოა
  // (`refreshSession` single-flight-ია), მერე თითოეული ზუსტად ერთხელ მეორდება.
  if (response.status === 401 && !retried && !isAuthPath(path)) {
    const token = await refreshSession();
    if (token) return request(path, { ...options, retried: true });
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

