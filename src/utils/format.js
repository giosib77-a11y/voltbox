import { CURRENCY_SYMBOL, LOW_STOCK_THRESHOLD } from '../constants/index.js';

/**
 * ფორმატირების ერთადერთი წყარო — ფასები, თარიღები, რიცხვები.
 * კომპონენტებში პირდაპირი toLocaleString / string-concat აკრძალულია.
 */

const KA_MONTHS = [
  'იანვარი',
  'თებერვალი',
  'მარტი',
  'აპრილი',
  'მაისი',
  'ივნისი',
  'ივლისი',
  'აგვისტო',
  'სექტემბერი',
  'ოქტომბერი',
  'ნოემბერი',
  'დეკემბერი',
];

/** ათასეულების გამყოფი: 2499 → "2 499" */
export function formatNumber(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '0';
  const [int, frac] = Math.abs(n).toFixed(Number.isInteger(n) ? 0 : 2).split('.');
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const sign = n < 0 ? '-' : '';
  return frac ? `${sign}${grouped}.${frac}` : `${sign}${grouped}`;
}

/** 2499 → "2 499 ₾" */
export function formatPrice(value) {
  return `${formatNumber(value)} ${CURRENCY_SYMBOL}`;
}

/** 0.15 არა — გვაძლევს მთელ პროცენტს: (2799, 2499) → 11 */
export function calcDiscountPercent(price, oldPrice) {
  if (!oldPrice || !price || oldPrice <= price) return 0;
  return Math.round(((oldPrice - price) / oldPrice) * 100);
}

/** 11 → "-11%" */
export function formatDiscount(percent) {
  return `-${Math.abs(Math.round(percent))}%`;
}

/** "2026-01-14T10:00:00Z" → "14 იანვარი, 2026" */
export function formatDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getDate()} ${KA_MONTHS[d.getMonth()]}, ${d.getFullYear()}`;
}

/** "2026-01-14T10:00:00Z" → "14 იანვარი, 2026 · 14:00" */
export function formatDateTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${formatDate(iso)} · ${hh}:${mm}`;
}

/** "555123456" → "555 12 34 56" */
export function formatPhone(value) {
  let digits = String(value || '').replace(/[^0-9]/g, '');
  // ქვეყნის კოდი (+995) ჩამოიჭრება, თუ მითითებულია
  if (digits.length > 9 && digits.startsWith('995')) digits = digits.slice(3);
  digits = digits.slice(0, 9);
  const parts = [digits.slice(0, 3), digits.slice(3, 5), digits.slice(5, 7), digits.slice(7, 9)];
  return parts.filter(Boolean).join(' ');
}

/** 4.62 → "4.6" */
export function formatRating(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '0.0';
  return n.toFixed(1);
}

/** "128 შეფასება" — ქართულში მრავლობითი ფორმა არ იცვლება. */
export function formatReviews(count) {
  return `${formatNumber(count)} შეფასება`;
}

export function formatItemsCount(count) {
  return `${formatNumber(count)} პროდუქტი`;
}

/** specs-ის მნიშვნელობა → ადამიანური ტექსტი (boolean-ების ჩათვლით). */
export function formatSpecValue(value) {
  if (value === true) return 'დიახ';
  if (value === false) return 'არა';
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

/** მარაგის ტექსტური სტატუსი. */
export function stockLabel(stock) {
  if (!stock || stock <= 0) return 'მარაგში არ არის';
  if (stock <= LOW_STOCK_THRESHOLD) return `ბოლო ${stock} ცალი`;
  return 'მარაგშია';
}

/** გრძელი ტექსტის მოკვეცა. */
export function truncate(text, max = 120) {
  const s = String(text || '');
  return s.length > max ? `${s.slice(0, max - 1).trimEnd()}…` : s;
}
