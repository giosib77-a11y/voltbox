/**
 * REST იმპლემენტაციის ჩონჩხი.
 *
 * ხელმოწერები *ზუსტად* ემთხვევა `mockApi.js`-ისას — გადართვა ხდება მხოლოდ
 * `.env`-ში `VITE_API_MODE=http`-ის მითითებით; არცერთი კომპონენტი არ იცვლება.
 *
 * თითოეულ ფუნქციასთან მითითებულია მისი endpoint.
 */

import { readJSON, removeKey, writeJSON } from '../utils/storage.js';
import { DEFAULT_LANGUAGE, currentLanguage } from '../i18n/index.js';
import { request } from './httpClient.js';
import { clearSession, readSession, writeSession } from './session.js';

/** სტუმრის შეკვეთების lookup token-ები — შეკვეთის დადასტურების გვერდისთვის. */
const GUEST_ORDERS_KEY = 'guest-orders:v2';

/** Held the phone given at checkout; dropped wherever the token store is touched. */
const LEGACY_GUEST_ORDERS_KEY = 'guest-orders:v1';

/* -------------------------------------------------------------------------- */
/*  კატალოგი                                                                   */
/* -------------------------------------------------------------------------- */

/**
 * `lang` for every request whose answer names a product, category or brand.
 *
 * The API answers in the language asked for, so the shopper downloads only
 * the text on their screen. An English page sends `lang=en`; a Georgian page
 * sends nothing, so its requests are exactly the ones it made before English
 * existed. A query parameter rather than a header: the URL is then the cache
 * key, and English and Georgian can never be served for each other.
 *
 * Read at call time. The page's language is fixed until the next load
 * (i18n/index.js) - the language switch is a page load - so nothing cached in
 * memory for a page, like the categories in hooks/useProducts.js, can hold the
 * other language.
 */
function lang() {
  const language = currentLanguage();
  return language === DEFAULT_LANGUAGE ? undefined : language;
}

// GET /products?category=&sort=&page=&limit=&q=&<filters>&lang=
export async function getProducts({ category, filters, sort, page, limit, q } = {}) {
  return request('/products', {
    params: { category, sort, page, limit, q, ...(filters || {}), lang: lang() },
  });
}

// GET /products/:slug?lang=
export async function getProductBySlug(slug) {
  return request(`/products/${encodeURIComponent(slug)}`, { params: { lang: lang() } });
}

// GET /products/by-id/:id?lang=
export async function getProductById(id) {
  return request(`/products/by-id/${encodeURIComponent(id)}`, { params: { lang: lang() } });
}

// GET /products/:id/related?limit=&lang=
export async function getRelatedProducts(id, limit = 4) {
  return request(`/products/${encodeURIComponent(id)}/related`, {
    params: { limit, lang: lang() },
  });
}

// GET /brands?lang=
export async function getBrands() {
  return request('/brands', { params: { lang: lang() } });
}

// GET /categories?lang=
// შენიშვნა: პროდუქტის პასუხში სასურველია `brandCountry` — mock იმპლემენტაცია მას
// `data/brands.js`-იდან ამატებს, backend-მა კი თავად უნდა დააბრუნოს.
export async function getCategories() {
  return request('/categories', { params: { lang: lang() } });
}

// GET /home-sections?lang=
export async function getHomeSections() {
  return request('/home-sections', { params: { lang: lang() } });
}

// GET /search?q=&limit=&lang= - matches either name in both languages; `lang`
// picks the one shown.
export async function searchProducts(q, limit = 5) {
  return request('/search', { params: { q, limit, lang: lang() } });
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
  rememberGuestOrder(order.orderNumber, order.lookupToken);
  return order;
}

/**
 * სტუმრის შეკვეთის lookup token-ს ლოკალურად ვინახავთ.
 *
 * შეკვეთის ნომერი თანმიმდევრობითია და გამოცნობადი, ტელეფონი კი სხვებმაც იციან,
 * ამიტომ სერვერი შეკვეთას მხოლოდ იმ შემთხვევით token-ზე გასცემს, რომელიც
 * შეკვეთისას ერთხელ დააბრუნა. A signed-in order gets none and stores nothing:
 * it is read through the account.
 */
function rememberGuestOrder(orderNumber, token) {
  removeKey(LEGACY_GUEST_ORDERS_KEY);
  if (!orderNumber || !token) return;
  const store = readJSON(GUEST_ORDERS_KEY, {});
  writeJSON(GUEST_ORDERS_KEY, { ...store, [orderNumber]: token });
}

/**
 * GET /delivery — ქალაქები, ტარიფები და უფასო მიწოდების ზღვარი.
 *
 * API ფულს სტრიქონად აბრუნებს ("8.00"); აქ ერთხელ ხდება რიცხვად, რომ
 * გვერდებმა შეადარონ და შეკრიბონ.
 */
export async function getDeliveryRules() {
  const rules = await request('/delivery');
  return {
    cities: (rules?.cities || []).map((city) => ({ name: city.name, fee: Number(city.fee) })),
    freeFrom: Number(rules?.freeFrom),
    currency: rules?.currency,
    // რას შეუძლია ეს deployment — იხ. hooks/useEmailEnabled.js
    features: { email: rules?.features?.email === true },
  };
}

// GET /orders
export async function getOrders() {
  return request('/orders');
}

/**
 * One order, by number.
 *
 * A signed-in caller reads their own with GET. A guest proves the order is
 * theirs with the token POST /orders returned, and that goes in a POST body,
 * never in the URL, where every access log, proxy log and history entry
 * between here and the server would keep it.
 */
export async function getOrderByNumber(orderNumber) {
  removeKey(LEGACY_GUEST_ORDERS_KEY);
  const token = readJSON(GUEST_ORDERS_KEY, {})[orderNumber];
  if (token) {
    return request('/orders/lookup', {
      method: 'POST',
      body: { orderNumber, token },
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

// POST /auth/forgot-password — the same answer whether or not the address has
// an account; the link, if any, arrives by email.
export async function requestPasswordReset({ email }) {
  return request('/auth/forgot-password', { method: 'POST', body: { email } });
}

// POST /auth/reset-password — works once per link and ends every session of
// the account, this browser's included.
export async function resetPassword({ token, newPassword }) {
  return request('/auth/reset-password', { method: 'POST', body: { token, newPassword } });
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

/* --- cart ------------------------------------------------------------------ */
//
// The browser stays the source of truth while shopping: every `+` and `-` is
// local and instant, and these calls are the copy that follows a signed-in
// shopper between devices. Only the id and quantity travel - the server reads
// the name, price and image back from the catalogue, so a saved cart can never
// quote a stale price.

/** Lines as the API takes them: everything else in a cart entry is local. */
function cartPayload(items = []) {
  return {
    items: items.map((item) => ({ productId: item.productId, qty: item.qty })),
  };
}

// GET /cart?lang=
export async function getCart() {
  const { items } = await request('/cart', { params: { lang: lang() } });
  return items;
}

// PUT /cart?lang=
export async function saveCart(items) {
  const { items: saved } = await request('/cart', {
    method: 'PUT',
    params: { lang: lang() },
    body: cartPayload(items),
  });
  return saved;
}

// POST /cart/merge?lang= — for signing in with a basket already in this
// browser, and on every signed-in page load. Its lines replace the ones on
// screen, names included, so they have to come back in the page's language.
export async function mergeCart(items) {
  const { items: merged } = await request('/cart/merge', {
    method: 'POST',
    params: { lang: lang() },
    body: cartPayload(items),
  });
  return merged;
}

// DELETE /cart
export async function clearCart() {
  return request('/cart', { method: 'DELETE' });
}

export const implementation = 'http';
export { ApiError, AuthError, ConflictError, NotFoundError, ValidationError } from './errors.js';
