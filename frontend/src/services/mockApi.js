/**
 * Mock იმპლემენტაცია — მუშაობს მეხსიერებაში, `data/products.js`-ზე.
 *
 * ყველა მეთოდი async-ია და ხელოვნურ დაყოვნებას (200–400ms) იძენს, რომ
 * loading-სთეითები რეალურ პირობებში გამოიცადოს.
 *
 * ⚠️  ეს ფაილი ერთადერთია, რომელიც `data/`-ს კითხულობს.
 */

import { products as rawProducts } from '../data/products.js';
import { categories, categoryLabels, getCategoryBySlug } from '../data/categories.js';
import { brandsByName } from '../data/brands.js';
import { searchProducts as runSearch } from '../utils/search.js';
import { applyFilters, computeFacets, paginate, sortProducts } from '../utils/filter.js';
import { calcDiscountPercent } from '../utils/format.js';
import { readJSON, writeJSON } from '../utils/storage.js';
import { DEFAULT_SORT, LOW_STOCK_THRESHOLD, PAGE_SIZE, STORAGE_KEYS } from '../constants/index.js';
import { calcTotals } from '../utils/pricing.js';
import { AuthError, NotFoundError, ValidationError } from './errors.js';

/* -------------------------------------------------------------------------- */
/*  დამხმარეები                                                                */
/* -------------------------------------------------------------------------- */

const MIN_DELAY = 200;
const MAX_DELAY = 400;

function delay() {
  const ms = MIN_DELAY + Math.random() * (MAX_DELAY - MIN_DELAY);
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

/** წარმოებული ველების დამატება — mock მონაცემებში ისინი ხელით არ წერია. */
function decorate(product) {
  const discountPercent = calcDiscountPercent(product.price, product.oldPrice);
  return {
    ...product,
    // ბრენდის ცნობარიდან — UI-ს `data/brands.js`-თან პირდაპირი კავშირი არ სჭირდება
    brandCountry: brandsByName[product.brand]?.country ?? null,
    discountPercent,
    hasDiscount: discountPercent > 0,
    inStock: product.stock > 0,
    isLowStock: product.stock > 0 && product.stock <= LOW_STOCK_THRESHOLD,
  };
}

/** ძებნის შედეგებში (კატეგორიათაშორისი) ხელმისაწვდომი ფილტრები. */
const GLOBAL_FILTERS = [
  { key: 'category', label: 'კატეგორია', type: 'checkbox' },
  { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
];

function filtersForCategory(categorySlug) {
  const category = categorySlug ? getCategoryBySlug(categorySlug) : null;
  return category ? category.filters : GLOBAL_FILTERS;
}

function nextId(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

/* -------------------------------------------------------------------------- */
/*  კატალოგი                                                                   */
/* -------------------------------------------------------------------------- */

/**
 * პროდუქტების სია ფილტრებით, სორტით და პაგინაციით.
 * @param {{ category?:string, filters?:object, sort?:string, page?:number, limit?:number, q?:string }} params
 * @returns {Promise<import('../types.js').ProductListResult>}
 */
export async function getProducts(params = {}) {
  await delay();
  const {
    category = null,
    filters = {},
    sort = DEFAULT_SORT,
    page = 1,
    limit = PAGE_SIZE,
    q = '',
  } = params;

  if (category && !getCategoryBySlug(category)) {
    throw new NotFoundError('ასეთი კატეგორია ვერ მოიძებნა');
  }

  let pool = category ? rawProducts.filter((p) => p.category === category) : rawProducts;
  const query = String(q || '').trim();
  if (query) pool = runSearch(pool, query, { categoryLabels });

  const categoryFilters = filtersForCategory(category);
  const facets = computeFacets(pool, filters, categoryFilters);
  const filtered = applyFilters(pool, filters, categoryFilters);

  // ძებნისას რელევანტურობა ნაგულისხმევია, სანამ მომხმარებელი სორტს არ შეცვლის
  const ordered = query && sort === 'relevance' ? filtered : sortProducts(filtered, sort);
  const paged = paginate(ordered, page, limit);

  return {
    items: paged.items.map(decorate),
    total: paged.total,
    page: paged.page,
    totalPages: paged.totalPages,
    limit: paged.limit,
    facets,
  };
}

/**
 * @param {string} slug
 * @returns {Promise<import('../types.js').DecoratedProduct>}
 * @throws {NotFoundError}
 */
export async function getProductBySlug(slug) {
  await delay();
  const product = rawProducts.find((p) => p.slug === slug);
  if (!product) throw new NotFoundError('ასეთი პროდუქტი ვერ მოიძებნა');
  return decorate(product);
}

export async function getProductById(id) {
  await delay();
  const product = rawProducts.find((p) => p.id === id);
  if (!product) throw new NotFoundError('ასეთი პროდუქტი ვერ მოიძებნა');
  return decorate(product);
}

/** მსგავსი პროდუქტები: იგივე კატეგორია, ფასის ±30% დიაპაზონი. */
export async function getRelatedProducts(id, limit = 4) {
  await delay();
  const source = rawProducts.find((p) => p.id === id);
  if (!source) return [];

  const min = source.price * 0.7;
  const max = source.price * 1.3;
  const sameCategory = rawProducts.filter((p) => p.category === source.category && p.id !== source.id);

  const inRange = sameCategory.filter((p) => p.price >= min && p.price <= max);
  const rest = sameCategory.filter((p) => p.price < min || p.price > max);

  const byCloseness = (a, b) => Math.abs(a.price - source.price) - Math.abs(b.price - source.price);
  const result = [...inRange.sort(byCloseness), ...rest.sort(byCloseness)].slice(0, limit);
  return result.map(decorate);
}

/** ბრენდების ცნობარი პროდუქტების რაოდენობით. */
export async function getBrands() {
  await delay();
  return Object.values(brandsByName).map((brand) => ({
    ...brand,
    productsCount: rawProducts.filter((p) => p.brand === brand.name).length,
  }));
}

export async function getCategories() {
  await delay();
  return categories.map((category) => ({
    ...category,
    productsCount: rawProducts.filter((p) => p.category === category.id).length,
  }));
}

/** მთავარი გვერდის სექციები ერთი გამოძახებით. */
export async function getHomeSections() {
  await delay();
  const decorated = rawProducts.map(decorate);

  const newArrivals = decorated
    .filter((p) => p.isNew)
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
    .slice(0, 8);

  const discounted = decorated
    .filter((p) => p.hasDiscount)
    .sort((a, b) => b.discountPercent - a.discountPercent)
    .slice(0, 8);

  const featured = decorated.filter((p) => p.isFeatured).slice(0, 8);

  const popularCategories = categories.map((category) => ({
    ...category,
    productsCount: rawProducts.filter((p) => p.category === category.id).length,
  }));

  return { newArrivals, discounted, featured, popularCategories };
}

/** Autocomplete-ისთვის — მსუბუქი, დაყოვნების გარეშე მაქსიმალურად სწრაფი. */
export async function searchProducts(q, limit = 5) {
  await delay();
  const query = String(q || '').trim();
  if (!query) return [];
  return runSearch(rawProducts, query, { limit, categoryLabels }).map(decorate);
}

/* -------------------------------------------------------------------------- */
/*  შეკვეთები                                                                  */
/* -------------------------------------------------------------------------- */

function readOrders() {
  const list = readJSON(STORAGE_KEYS.orders, []);
  return Array.isArray(list) ? list : [];
}

function generateOrderNumber() {
  const now = new Date();
  const yy = String(now.getFullYear()).slice(-2);
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const rand = Math.floor(1000 + Math.random() * 9000);
  return `VB-${yy}${mm}-${rand}`;
}

/**
 * შეკვეთის შექმნა. რეგისტრაცია სავალდებულო არ არის.
 * @param {object} payload { items, customer, paymentMethod }
 */
export async function createOrder(payload) {
  // `payload.idempotencyKey` აქ განზრახ იგნორირდება: mock ერთ ჩანართშია და
  // ორმაგი გაგზავნის რბოლა არ არსებობს. ხელმოწერა httpApi-სას ემთხვევა.
  await delay();
  const items = Array.isArray(payload?.items) ? payload.items : [];
  if (!items.length) throw new ValidationError('კალათა ცარიელია');
  if (!payload?.customer?.phone) throw new ValidationError('ტელეფონის ნომერი სავალდებულოა');

  const totals = calcTotals(items.map((i) => ({ price: i.snapshot.price, qty: i.qty })));
  const session = readJSON(STORAGE_KEYS.auth, null);

  const order = {
    orderNumber: generateOrderNumber(),
    createdAt: new Date().toISOString(),
    status: 'pending',
    userId: session?.user?.id ?? null,
    items,
    customer: payload.customer,
    paymentMethod: payload.paymentMethod || 'cash',
    totals: { subtotal: totals.subtotal, shipping: totals.shipping, total: totals.total },
  };

  writeJSON(STORAGE_KEYS.orders, [order, ...readOrders()]);
  return order;
}

export async function getOrders() {
  await delay();
  const session = readJSON(STORAGE_KEYS.auth, null);
  const userId = session?.user?.id ?? null;
  // ავტორიზებული ხედავს თავის შეკვეთებს + ამ ბრაუზერში სტუმრად გაკეთებულებს
  return readOrders().filter((o) => (userId ? o.userId === userId || o.userId === null : true));
}

export async function getOrderByNumber(orderNumber) {
  await delay();
  const order = readOrders().find((o) => o.orderNumber === orderNumber);
  if (!order) throw new NotFoundError('ასეთი შეკვეთა ვერ მოიძებნა');
  return order;
}

/* -------------------------------------------------------------------------- */
/*  ავტორიზაცია                                                                */
/*                                                                             */
/*  ⚠️  MOCK ONLY — replace with real auth API.                                 */
/*  პაროლები ინახება მხოლოდ base64-ით დაფარულად, რაც უსაფრთხოებას *არ*         */
/*  უზრუნველყოფს. რეალურ backend-ზე გადასვლისას მთელი ეს ბლოკი იშლება.         */
/* -------------------------------------------------------------------------- */

function obfuscate(password) {
  // MOCK ONLY — არავითარი კრიპტოგრაფიული ღირებულება
  try {
    return btoa(unescape(encodeURIComponent(`vb::${password}`)));
  } catch {
    return `vb::${password}`;
  }
}

function readUsers() {
  const list = readJSON(STORAGE_KEYS.users, []);
  return Array.isArray(list) ? list : [];
}

function publicUser(user) {
  const { passwordHash, ...rest } = user;
  return rest;
}

function requireSession() {
  const session = readJSON(STORAGE_KEYS.auth, null);
  if (!session?.user?.id) throw new AuthError('გთხოვთ, გაიაროთ ავტორიზაცია');
  return session;
}

export async function register({ firstName, lastName, email, password }) {
  await delay();
  const normalizedEmail = String(email || '').trim().toLowerCase();
  const users = readUsers();

  if (users.some((u) => u.email === normalizedEmail)) {
    throw new ValidationError('ამ ელ. ფოსტით მომხმარებელი უკვე რეგისტრირებულია', { email: true });
  }

  const user = {
    id: nextId('usr'),
    firstName: String(firstName || '').trim(),
    lastName: String(lastName || '').trim(),
    email: normalizedEmail,
    phone: '',
    createdAt: new Date().toISOString(),
    passwordHash: obfuscate(password),
  };

  writeJSON(STORAGE_KEYS.users, [...users, user]);
  const session = { user: publicUser(user), token: nextId('tok') };
  writeJSON(STORAGE_KEYS.auth, session);
  return session;
}

export async function login({ email, password }) {
  await delay();
  const normalizedEmail = String(email || '').trim().toLowerCase();
  const user = readUsers().find((u) => u.email === normalizedEmail);

  if (!user || user.passwordHash !== obfuscate(password)) {
    throw new AuthError('ელ. ფოსტა ან პაროლი არასწორია');
  }

  const session = { user: publicUser(user), token: nextId('tok') };
  writeJSON(STORAGE_KEYS.auth, session);
  return session;
}

export async function logout() {
  await delay();
  writeJSON(STORAGE_KEYS.auth, null);
  return { ok: true };
}

export async function getProfile() {
  await delay();
  const session = requireSession();
  const user = readUsers().find((u) => u.id === session.user.id);
  if (!user) throw new AuthError('სესია აღარ არის აქტიური');
  return publicUser(user);
}

export async function updateProfile(patch) {
  await delay();
  const session = requireSession();
  const users = readUsers();
  const index = users.findIndex((u) => u.id === session.user.id);
  if (index === -1) throw new AuthError('სესია აღარ არის აქტიური');

  const updated = { ...users[index], ...patch, id: users[index].id, passwordHash: users[index].passwordHash };
  users[index] = updated;
  writeJSON(STORAGE_KEYS.users, users);
  writeJSON(STORAGE_KEYS.auth, { ...session, user: publicUser(updated) });
  return publicUser(updated);
}

export async function changePassword({ currentPassword, newPassword }) {
  await delay();
  const session = requireSession();
  const users = readUsers();
  const index = users.findIndex((u) => u.id === session.user.id);
  if (index === -1) throw new AuthError('სესია აღარ არის აქტიური');
  if (users[index].passwordHash !== obfuscate(currentPassword)) {
    throw new ValidationError('მიმდინარე პაროლი არასწორია', { currentPassword: true });
  }

  users[index] = { ...users[index], passwordHash: obfuscate(newPassword) };
  writeJSON(STORAGE_KEYS.users, users);
  return { ok: true };
}

/** სესიის აღდგენა გვერდის გადატვირთვისას (ქსელის გარეშე). */
export function getSessionSync() {
  const session = readJSON(STORAGE_KEYS.auth, null);
  return session?.user ? session : null;
}

/* -------------------------------------------------------------------------- */
/*  მისამართები                                                                */
/* -------------------------------------------------------------------------- */

function readAddresses() {
  const list = readJSON(STORAGE_KEYS.addresses, []);
  return Array.isArray(list) ? list : [];
}

export async function getAddresses() {
  await delay();
  const session = requireSession();
  return readAddresses().filter((a) => a.userId === session.user.id);
}

export async function saveAddress(address) {
  await delay();
  const session = requireSession();
  const all = readAddresses();
  const isDefault = Boolean(address.isDefault);

  let next;
  if (address.id) {
    next = all.map((a) => (a.id === address.id ? { ...a, ...address } : a));
  } else {
    next = [...all, { ...address, id: nextId('adr'), userId: session.user.id }];
  }
  if (isDefault) {
    next = next.map((a) =>
      a.userId === session.user.id ? { ...a, isDefault: a.id === (address.id || next[next.length - 1].id) } : a,
    );
  }
  writeJSON(STORAGE_KEYS.addresses, next);
  return next.filter((a) => a.userId === session.user.id);
}

export async function deleteAddress(id) {
  await delay();
  const session = requireSession();
  const next = readAddresses().filter((a) => a.id !== id);
  writeJSON(STORAGE_KEYS.addresses, next);
  return next.filter((a) => a.userId === session.user.id);
}

/** დიაგნოსტიკისთვის — რომელი იმპლემენტაცია მუშაობს. */
export const implementation = 'mock';
export { ApiError, AuthError, ConflictError, NotFoundError, ValidationError } from './errors.js';
