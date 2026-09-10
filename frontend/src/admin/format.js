/**
 * Formatting for the admin panel.
 *
 * What it does: money and dates, in the store's locale and timezone.
 * Where it fits: every admin table and detail view.
 * Notes: the API returns money as a number with two decimals and never expects
 * the client to do arithmetic on it. These functions only display.
 */

const MONEY = new Intl.NumberFormat('ka-GE', {
  style: 'currency',
  currency: 'GEL',
  minimumFractionDigits: 2,
});

const DATE_TIME = new Intl.DateTimeFormat('ka-GE', {
  // The store's day, not the viewer's: an order placed at 01:00 Tbilisi time
  // must not read as the previous day for an admin travelling abroad.
  timeZone: 'Asia/Tbilisi',
  dateStyle: 'medium',
  timeStyle: 'short',
});

const DATE_ONLY = new Intl.DateTimeFormat('ka-GE', {
  timeZone: 'Asia/Tbilisi',
  dateStyle: 'medium',
});

/** `1234.5` → `1 234,50 ₾`. Accepts the string form the API may send. */
export function money(value) {
  if (value === null || value === undefined || value === '') return '—';
  const amount = typeof value === 'string' ? Number(value) : value;
  return Number.isFinite(amount) ? MONEY.format(amount) : '—';
}

/** ISO timestamp → date and time in the store's timezone. */
export function dateTime(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : DATE_TIME.format(parsed);
}

/** ISO timestamp → date only. */
export function dateOnly(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : DATE_ONLY.format(parsed);
}
