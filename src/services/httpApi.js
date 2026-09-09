/**
 * REST იმპლემენტაციის ჩონჩხი.
 *
 * ხელმოწერები *ზუსტად* ემთხვევა `mockApi.js`-ისას — გადართვა ხდება მხოლოდ
 * `.env`-ში `VITE_API_MODE=http`-ის მითითებით; არცერთი კომპონენტი არ იცვლება.
 *
 * TODO: connect backend — თითოეულ ფუნქციაში მითითებულია მოსალოდნელი endpoint.
 */

import { ApiError, AuthError, NotFoundError, ValidationError } from './errors.js';
import { STORAGE_KEYS } from '../constants/index.js';
import { readJSON, writeJSON } from '../utils/storage.js';

const BASE_URL = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');

/** ავტორიზაციის ტოკენი — რეალურ backend-ზე httpOnly cookie სჯობს. */
function authHeader() {
  const session = readJSON(STORAGE_KEYS.auth, null);
  return session?.token ? { Authorization: `Bearer ${session.token}` } : {};
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

/** ერთიანი fetch wrapper — შეცდომებს იმავე კლასებად აქცევს, რასაც mock. */
async function request(path, { method = 'GET', body, params, signal } = {}) {
  const url = `${BASE_URL}${path}${toQuery(params)}`;

  let response;
  try {
    response = await fetch(url, {
      method,
      signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...authHeader(),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (cause) {
    throw new ApiError('სერვერთან კავშირი ვერ დამყარდა', 0, cause);
  }

  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (response.ok) return payload;

  const message = payload?.message || 'მოთხოვნის დამუშავება ვერ მოხერხდა';
  if (response.status === 404) throw new NotFoundError(message);
  if (response.status === 401 || response.status === 403) throw new AuthError(message);
  if (response.status === 422 || response.status === 400) {
    throw new ValidationError(message, payload?.errors || null);
  }
  throw new ApiError(message, response.status, payload);
}

/* -------------------------------------------------------------------------- */
/*  კატალოგი                                                                   */
/* -------------------------------------------------------------------------- */

// TODO: connect backend — GET /products?category=&sort=&page=&limit=&q=&<filters>
export async function getProducts({ category, filters, sort, page, limit, q } = {}) {
  return request('/products', { params: { category, sort, page, limit, q, ...(filters || {}) } });
}

// TODO: connect backend — GET /products/:slug
export async function getProductBySlug(slug) {
  return request(`/products/${encodeURIComponent(slug)}`);
}

// TODO: connect backend — GET /products/by-id/:id
export async function getProductById(id) {
  return request(`/products/by-id/${encodeURIComponent(id)}`);
}

// TODO: connect backend — GET /products/:id/related?limit=
export async function getRelatedProducts(id, limit = 4) {
  return request(`/products/${encodeURIComponent(id)}/related`, { params: { limit } });
}

// TODO: connect backend — GET /brands
export async function getBrands() {
  return request('/brands');
}

// TODO: connect backend — GET /categories
// შენიშვნა: პროდუქტის პასუხში სასურველია `brandCountry` — mock იმპლემენტაცია მას
// `data/brands.js`-იდან ამატებს, backend-მა კი თავად უნდა დააბრუნოს.
export async function getCategories() {
  return request('/categories');
}

// TODO: connect backend — GET /home-sections
export async function getHomeSections() {
  return request('/home-sections');
}

// TODO: connect backend — GET /search?q=&limit=
export async function searchProducts(q, limit = 5) {
  return request('/search', { params: { q, limit } });
}

/* -------------------------------------------------------------------------- */
/*  შეკვეთები                                                                  */
/* -------------------------------------------------------------------------- */

// TODO: connect backend — POST /orders
export async function createOrder(payload) {
  return request('/orders', { method: 'POST', body: payload });
}

// TODO: connect backend — GET /orders
export async function getOrders() {
  return request('/orders');
}

// TODO: connect backend — GET /orders/:orderNumber
export async function getOrderByNumber(orderNumber) {
  return request(`/orders/${encodeURIComponent(orderNumber)}`);
}

/* -------------------------------------------------------------------------- */
/*  ავტორიზაცია                                                                */
/* -------------------------------------------------------------------------- */

// TODO: connect backend — POST /auth/register  → { user, token }
export async function register(payload) {
  const session = await request('/auth/register', { method: 'POST', body: payload });
  writeJSON(STORAGE_KEYS.auth, session);
  return session;
}

// TODO: connect backend — POST /auth/login  → { user, token }
export async function login(payload) {
  const session = await request('/auth/login', { method: 'POST', body: payload });
  writeJSON(STORAGE_KEYS.auth, session);
  return session;
}

// TODO: connect backend — POST /auth/logout
export async function logout() {
  try {
    await request('/auth/logout', { method: 'POST' });
  } finally {
    writeJSON(STORAGE_KEYS.auth, null);
  }
  return { ok: true };
}

// TODO: connect backend — GET /auth/me
export async function getProfile() {
  return request('/auth/me');
}

// TODO: connect backend — PATCH /auth/me
export async function updateProfile(patch) {
  return request('/auth/me', { method: 'PATCH', body: patch });
}

// TODO: connect backend — POST /auth/change-password
export async function changePassword(payload) {
  return request('/auth/change-password', { method: 'POST', body: payload });
}

/** სესიის სინქრონული აღდგენა — ტოკენი ლოკალურად ინახება. */
export function getSessionSync() {
  const session = readJSON(STORAGE_KEYS.auth, null);
  return session?.user ? session : null;
}

/* -------------------------------------------------------------------------- */
/*  მისამართები                                                                */
/* -------------------------------------------------------------------------- */

// TODO: connect backend — GET /addresses
export async function getAddresses() {
  return request('/addresses');
}

// TODO: connect backend — POST /addresses  |  PUT /addresses/:id
export async function saveAddress(address) {
  if (address.id) return request(`/addresses/${encodeURIComponent(address.id)}`, { method: 'PUT', body: address });
  return request('/addresses', { method: 'POST', body: address });
}

// TODO: connect backend — DELETE /addresses/:id
export async function deleteAddress(id) {
  return request(`/addresses/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export const implementation = 'http';
export { ApiError, AuthError, NotFoundError, ValidationError };
