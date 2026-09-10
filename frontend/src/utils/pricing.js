import { SHIPPING } from '../constants/index.js';

/**
 * კალათის ფულადი ლოგიკა — ერთ ადგილას.
 * კომპონენტებში მიწოდების ფასი არასდროს არ იწერება ხელით.
 */

/** @returns {number} მიწოდების ღირებულება მოცემულ subtotal-ზე */
export function calcShipping(subtotal) {
  if (!subtotal || subtotal <= 0) return 0;
  return subtotal >= SHIPPING.freeThreshold ? 0 : SHIPPING.flatFee;
}

/** რამდენი აკლია უფასო მიწოდებამდე (0 თუ უკვე უფასოა) */
export function amountToFreeShipping(subtotal) {
  return Math.max(0, SHIPPING.freeThreshold - (subtotal || 0));
}

export function isFreeShipping(subtotal) {
  return calcShipping(subtotal) === 0 && subtotal > 0;
}

/**
 * @param {{price:number, qty:number}[]} lines
 * @returns {{subtotal:number, shipping:number, total:number, itemsCount:number, savings:number}}
 */
export function calcTotals(lines = []) {
  const subtotal = lines.reduce((sum, l) => sum + Number(l.price || 0) * Number(l.qty || 0), 0);
  const itemsCount = lines.reduce((sum, l) => sum + Number(l.qty || 0), 0);
  const savings = lines.reduce((sum, l) => {
    const old = Number(l.oldPrice || 0);
    return old > l.price ? sum + (old - Number(l.price)) * Number(l.qty || 0) : sum;
  }, 0);
  const shipping = calcShipping(subtotal);
  return {
    subtotal: round2(subtotal),
    shipping,
    total: round2(subtotal + shipping),
    itemsCount,
    savings: round2(savings),
  };
}

function round2(n) {
  return Math.round((Number(n) + Number.EPSILON) * 100) / 100;
}
