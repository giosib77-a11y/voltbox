import { SHIPPING } from '../constants/index.js';

/**
 * კალათის ფულადი ლოგიკა — ერთ ადგილას.
 * კომპონენტებში მიწოდების ფასი არასდროს არ იწერება ხელით.
 */

/**
 * ფული მთელ თეთრებში — ერთადერთი ადგილი, სადაც ეს გარდაქმნა ხდება.
 *
 * A basket of 1.05 × 2 and 49.30 × 3 is 150.00 to the tetri and
 * 149.99999999999997 in IEEE754. Compared as floats that is below the
 * free-shipping threshold, so the page charged 5 ₾ while the server - which
 * counts in `Decimal` - charged nothing. The customer was quoted 155 and billed
 * 150, on the one basket where the promise is being tested.
 */
function toTetri(value) {
  return Math.round((Number(value) || 0) * 100);
}

const FREE_FROM_TETRI = toTetri(SHIPPING.freeThreshold);

/** @returns {number} მიწოდების ღირებულება მოცემულ subtotal-ზე */
export function calcShipping(subtotal) {
  const tetri = toTetri(subtotal);
  if (tetri <= 0) return 0;
  return tetri >= FREE_FROM_TETRI ? 0 : SHIPPING.flatFee;
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
  // Summed in whole tetri so the figure shown and the figure compared against
  // the threshold are the same number, and both match what the server computes.
  const subtotalTetri = lines.reduce(
    (sum, l) => sum + toTetri(l.price) * (Math.round(Number(l.qty)) || 0),
    0,
  );
  const itemsCount = lines.reduce((sum, l) => sum + (Math.round(Number(l.qty)) || 0), 0);
  const savingsTetri = lines.reduce((sum, l) => {
    const old = toTetri(l.oldPrice);
    const price = toTetri(l.price);
    return old > price ? sum + (old - price) * (Math.round(Number(l.qty)) || 0) : sum;
  }, 0);

  const subtotal = subtotalTetri / 100;
  const shipping = calcShipping(subtotal);
  return {
    subtotal,
    shipping,
    total: (subtotalTetri + toTetri(shipping)) / 100,
    itemsCount,
    savings: savingsTetri / 100,
  };
}
