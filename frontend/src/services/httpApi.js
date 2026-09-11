/**
 * REST იმპლემენტაციის ჩონჩხი.
 *
 * ხელმოწერები *ზუსტად* ემთხვევა `mockApi.js`-ისას — გადართვა ხდება მხოლოდ
 * `.env`-ში `VITE_API_MODE=http`-ის მითითებით; არცერთი კომპონენტი არ იცვლება.
 *
 * თითოეულ ფუნქციასთან მითითებულია მისი endpoint.
 */

import { readJSON, writeJSON } from '../utils/storage.js';
import { request } from './httpClient.js';
import { clearSession, readSession, writeSession } from './session.js';

/** სტუმრის შეკვეთების კონტაქტები — შეკვეთის დადასტურების გვერდისთვის. */
const GUEST_ORDERS_KEY = 'guest-orders:v1';

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
    // Idempotency-Key header-ია და არა ველი: body-ს `extra="forbid"` აქვს და
    // უცნობი ველი 400-ს გამოიწვევდა
    headers: payload.idempotencyKey ? { 'Idempotency-Key': payload.idempotencyKey } : undefined,
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

/**
 * One order, by number.
 *
 * A signed-in caller reads their own with GET. A guest has to prove the order
 * is theirs with the contact they gave at checkout, and that goes in a POST
 * body: it used to travel as `?email=` while actually carrying a phone number,
 * which wrote a customer's phone into every access log, proxy log and history
 * entry between here and the server.
 */
export async function getOrderByNumber(orderNumber) {
  const contact = readJSON(GUEST_ORDERS_KEY, {})[orderNumber];
  if (contact) {
    return request('/orders/lookup', {
      method: 'POST',
      body: { orderNumber, contact },
    });
  }
  return request(`/orders/${encodeURIComponent(orderNumber)}`);
}

/* -------------------------------------------------------------------------- */
/*  ავტორიზაცია                                                                */
/* -------------------------------------------------------------------------- */

// POST /auth/register  → { user, token }
export async function register(payload) {
  // მხოლოდ ის ველები, რასაც API იღებს. ფორმა `confirmPassword`-საც ატარებს —
  // ის ვალიდაციისთვისაა და სერვერს არ სჭირდება. `ApiRequest`-ს `extra="forbid"`
  // აქვს, ამიტომ მისი გაგზავნა 400-ს იწვევდა: რეგისტრაცია საერთოდ არ მუშაობდა.
  const session = await request('/auth/register', {
    method: 'POST',
    body: {
      firstName: payload.firstName,
      lastName: payload.lastName,
      email: payload.email,
      password: payload.password,
    },
  });
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
  // სერვერზე მაინც მოქმედი დარჩებოდა. The token itself is not ours to send:
  // it is in an httpOnly cookie, which the browser attaches and the server
  // both revokes and clears.
  try {
    await request('/auth/logout', { method: 'POST' });
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
export { ApiError, AuthError, ConflictError, NotFoundError, ValidationError } from './errors.js';
