import { formatPrice } from '../../utils/format.js';

/** Every city of GET /delivery with its fee, as "City — 11 ₾, City — 7 ₾". */
export function cityFees(rules) {
  return (rules?.cities || []).map((c) => `${c.name} — ${formatPrice(c.fee)}`).join(', ');
}

/**
 * Which payment sentence is true for the rules in GET /delivery.
 *
 * Returns the key suffix and the card cities: '' when every city takes the card,
 * 'Some' (with the list) when only some do, 'Cash' when none does - and while the
 * rules are not here yet, since cash on delivery is the one claim that always holds.
 */
export function cardVariant(rules) {
  const cities = rules?.cities || [];
  const card = cities.filter((city) => city.cardOnDelivery).map((city) => city.name);
  if (card.length === 0) return { suffix: 'Cash', cities: '' };
  if (card.length === cities.length) return { suffix: '', cities: '' };
  return { suffix: 'Some', cities: card.join(', ') };
}
