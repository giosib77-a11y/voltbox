/**
 * REST იმპლემენტაციის ჩონჩხი.
 *
 * ხელმოწერები *ზუსტად* ემთხვევა `mockApi.js`-ისას — გადართვა ხდება მხოლოდ
 * `.env`-ში `VITE_API_MODE=http`-ის მითითებით; არცერთი კომპონენტი არ იცვლება.
 *
 * თითოეულ ფუნქციასთან მითითებულია მისი endpoint.
 */

import { ApiError, AuthError, ConflictError, NotFoundError, ValidationError } from './errors.js';
import { readJSON, writeJSON } from '../utils/storage.js';
import {
  clearSession,
  getAccessToken,
  isAuthPath,
  readSession,
  refreshSession,
  writeSession,
} from './session.js';

const BASE_URL = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');

/** სტუმრის შეკვეთების კონტაქტები — შეკვეთის დადასტურების გვერდისთვის. */
const GUEST_ORDERS_KEY = 'guest-orders:v1';

/** ავტორიზაციის ტოკენი — რეალურ backend-ზე httpOnly cookie სჯობს. */
function authHeader() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
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
  return {
    message: envelope?.message || 'მოთხოვნის დამუშავება ვერ მოხერხდა',
    code: envelope?.code || null,
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
async function request(path, options = {}) {
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
  if (response.status === 401 || response.status === 403) throw new AuthError(message);
  if (response.status === 422 || response.status === 400) {
    throw new ValidationError(message, { code, details });
  }
  throw new ApiError(message, response.status, { code, details });
}

/* -------------------------------------------------------------------------- */
/*  კატალოგი                                                                   */
/* -------------------------------------------------------------------------- */

// GET /products?category=&sort=&page=&limit=&q=&<filters>
export async function getProducts({ category, filters, sort, page, limit, q } = {}) {
  return request('/products', { params: { category, sort, page, limit, q, ...(filters || {}) } });
}

// GET /products/:slug
export async function getProductBySlug(slug) {
  return request(`/products/${encodeURIComponent(slug)}`);
}

// GET /products/by-id/:id
export async function getProductById(id) {
  return request(`/products/by-id/${encodeURIComponent(id)}`);
}

// GET /products/:id/related?limit=
export async function getRelatedProducts(id, limit = 4) {
  return request(`/products/${encodeURIComponent(id)}/related`, { params: { limit } });
}

// GET /brands
export async function getBrands() {
  return request('/brands');
}

// GET /categories
// შენიშვნა: პროდუქტის პასუხში სასურველია `brandCountry` — mock იმპლემენტაცია მას
// `data/brands.js`-იდან ამატებს, backend-მა კი თავად უნდა დააბრუნოს.
export async function getCategories() {
  return request('/categories');
}

// GET /home-sections
export async function getHomeSections() {
  return request('/home-sections');
}

// GET /search?q=&limit=
export async function searchProducts(q, limit = 5) {
  return request('/search', { params: { q, limit } });
}

/* -------------------------------------------------------------------------- */
/*  შეკვეთები                                                                  */
/* -------------------------------------------------------------------------- */

// POST /orders
export async function createOrder(payload) {
  // სერვერს მხოლოდ productId და qty მიაქვს — ფასს ის თავად განსაზღვრავს ბაზიდან.
  // `snapshot` კალათის ლოკალური ქეშია; მისი გაგზავნა 400-ს იწვევს (extra="forbid"),
  // რაც განზრახაა: ფასის გაყალბების მცდელობა ჩუმად არ უნდა ჩაიაროს.
  const order = await request('/orders', {
    method: 'POST',
    body: {
      items: payload.items.map((item) => ({ productId: item.productId, qty: item.qty })),
      customer: payload.customer,
      paymentMethod: payload.paymentMethod,
    },
  });
  rememberGuestOrder(order.orderNumber, payload.customer?.phone);
  return order;
}

/**
 * სტუმრის შეკვეთის კონტაქტს ლოკალურად ვინახავთ.
 *
 * შეკვეთის ნომერი თანმიმდევრობითია და გამოცნობადი, ამიტომ სერვერი მარტო ნომრით
 * არ გასცემს შეკვეთას — სტუმარმა კონტაქტი უნდა დაამთხვიოს.
 */
function rememberGuestOrder(orderNumber, contact) {
  if (!orderNumber || !contact) return;
  const store = readJSON(GUEST_ORDERS_KEY, {});
  writeJSON(GUEST_ORDERS_KEY, { ...store, [orderNumber]: contact });
}

// GET /orders
export async function getOrders() {
  return request('/orders');
}

// GET /orders/:orderNumber
export async function getOrderByNumber(orderNumber) {
  const contact = readJSON(GUEST_ORDERS_KEY, {})[orderNumber];
  return request(`/orders/${encodeURIComponent(orderNumber)}`, {
    params: contact ? { email: contact } : undefined,
  });
}

/* -------------------------------------------------------------------------- */
/*  ავტორიზაცია                                                                */
/* -------------------------------------------------------------------------- */

// POST /auth/register  → { user, token }
export async function register(payload) {
  const session = await request('/auth/register', { method: 'POST', body: payload });
  writeSession(session);
  return session;
}

// POST /auth/login  → { user, token }
export async function login(payload) {
  const session = await request('/auth/login', { method: 'POST', body: payload });
  writeSession(session);
  return session;
}

// POST /auth/logout
export async function logout() {
  // ტოკენის ლოკალური წაშლა საკმარისი არაა — მოპარული refresh-ტოკენი
  // სერვერზე მაინც მოქმედი დარჩებოდა
  const session = readSession();
  try {
    await request('/auth/logout', {
      method: 'POST',
      body: { refreshToken: session?.refreshToken ?? null },
    });
  } finally {
    clearSession();
  }
  return { ok: true };
}

// GET /auth/me
export async function getProfile() {
  return request('/auth/me');
}

// PATCH /auth/me
export async function updateProfile(patch) {
  return request('/auth/me', { method: 'PATCH', body: patch });
}

// POST /auth/change-password
export async function changePassword(payload) {
  return request('/auth/change-password', { method: 'POST', body: payload });
}

/** სესიის სინქრონული აღდგენა — ტოკენი ლოკალურად ინახება. */
export function getSessionSync() {
  const session = readSession();
  return session?.user ? session : null;
}

/* -------------------------------------------------------------------------- */
/*  მისამართები                                                                */
/* -------------------------------------------------------------------------- */

// GET /addresses
export async function getAddresses() {
  return request('/addresses');
}

// POST /addresses  |  PUT /addresses/:id
export async function saveAddress(address) {
  if (address.id) return request(`/addresses/${encodeURIComponent(address.id)}`, { method: 'PUT', body: address });
  return request('/addresses', { method: 'POST', body: address });
}

// DELETE /addresses/:id
export async function deleteAddress(id) {
  return request(`/addresses/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export const implementation = 'http';
export { ApiError, AuthError, NotFoundError, ValidationError };
