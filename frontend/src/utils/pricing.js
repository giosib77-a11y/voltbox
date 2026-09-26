/**
 * კალათის ფულადი ლოგიკა — ერთ ადგილას.
 * კომპონენტებში მიწოდების ფასი არასდროს არ იწერება ხელით.
 *
 * მიწოდების წესები (ქალაქები, ტარიფები, უფასო მიწოდების ზღვარი) აქ არ ცხოვრობს:
 * ისინი `GET /delivery`-დან მოდის (hooks/useDeliveryRules.js) და არგუმენტად
 * გადმოეცემა. `rules` არის `{ cities: [{ name, fee }], freeFrom }`, რიცხვებით.
 * სერვერი იმავე ცხრილით ითვლის, ამიტომ ნაჩვენები და ჩამოჭრილი ერთი და იგივეა.
 */

/**
 * ფული მთელ თეთრებში — ერთადერთი ადგილი, სადაც ეს გარდაქმნა ხდება.
 *
 * A basket of 1.05 × 2 and 49.30 × 3 is 150.00 to the tetri and
 * 149.99999999999997 in IEEE754. Compared as floats that is below a threshold
 * of 150, so the page charged the fee while the server - which counts in
 * `Decimal` - charged nothing. The customer was quoted one total and billed
 * another, on the one basket where the promise is being tested.
 */
function toTetri(value) {
  return Math.round((Number(value) || 0) * 100);
}

function reachesFree(subtotal, rules) {
  return toTetri(subtotal) >= toTetri(rules.freeFrom);
}

/**
 * მიწოდების ღირებულება, ან `null`, როცა ჯერ უცნობია.
 *
 * უცნობია, სანამ წესები არ ჩატვირთულა, ან ქალაქი არჩეული არ არის (ან სიაში
 * არ არის) და კალათა ზღვარს ქვემოთაა. ზღვარს ზემოთ ქალაქი აღარ მნიშვნელობს —
 * ყველგან უფასოა.
 *
 * @param {number} subtotal
 * @param {{cities:{name:string, fee:number}[], freeFrom:number} | null} rules
 * @param {string} [city]
 * @returns {number | null}
 */
export function deliveryFee(subtotal, rules, city) {
  if (!rules) return null;
  if (reachesFree(subtotal, rules)) return 0;
  const entry = rules.cities.find((c) => c.name === city);
  return entry ? entry.fee : null;
}

/** რამდენი აკლია უფასო მიწოდებამდე (0, თუ უკვე უფასოა ან წესები უცნობია). */
export function amountToFreeDelivery(subtotal, rules) {
  if (!rules) return 0;
  return Math.max(0, toTetri(rules.freeFrom) - toTetri(subtotal)) / 100;
}

/** ჯამი მიწოდებით, თეთრებში შეკრებილი; `null`, როცა მიწოდება უცნობია. */
export function totalWithDelivery(subtotal, fee) {
  if (fee === null || fee === undefined) return null;
  return (toTetri(subtotal) + toTetri(fee)) / 100;
}

/**
 * @param {{price:number, qty:number, oldPrice?:number}[]} lines
 * @returns {{subtotal:number, itemsCount:number, savings:number}}
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

  return {
    subtotal: subtotalTetri / 100,
    itemsCount,
    savings: savingsTetri / 100,
  };
}

/**
 * A stored order's amounts as numbers, with `null` for any the order lacks.
 *
 * The API sends money as strings ("8.00"), so `shipping === 0` was never true
 * over http and a free delivery showed as "0 ₾". And an order saved without a
 * separate fee - an old mock-mode order in localStorage - has only a total; it
 * shows that, rather than a delivery line reading "0 ₾" it never had.
 *
 * @param {{subtotal?:number|string, shipping?:number|string, total?:number|string}} [totals]
 */
export function orderAmounts(totals = {}) {
  const read = (value) => {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const subtotal = read(totals?.subtotal);
  const shipping = read(totals?.shipping);
  return {
    subtotal: shipping === null ? null : subtotal,
    shipping: subtotal === null ? null : shipping,
    total: read(totals?.total) ?? 0,
  };
}
