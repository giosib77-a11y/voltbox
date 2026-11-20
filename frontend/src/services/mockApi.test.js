/**
 * The mock createOrder follows the server's card rule: card_on_delivery is
 * taken only in a city whose delivery rule says cardOnDelivery, and refused
 * otherwise with PAYMENT_METHOD_UNAVAILABLE. The shipped mock table lets both
 * cities take the card, so the table is replaced here with one that does not.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../data/delivery.js', () => ({
  deliveryRules: {
    cities: [
      { name: 'თბილისი', fee: 11, cardOnDelivery: true },
      { name: 'რუსთავი', fee: 7, cardOnDelivery: false },
    ],
    freeFrom: 100,
    currency: 'GEL',
    features: { email: false },
  },
}));

import { createOrder } from './mockApi.js';

const order = (city, paymentMethod) => ({
  items: [{ productId: 'p1', qty: 1, snapshot: { price: 40 } }],
  customer: { phone: '555123456', city, address: 'ჭავჭავაძის 42' },
  paymentMethod,
});

beforeEach(() => {
  localStorage.clear();
});

describe('mock createOrder and the card', () => {
  it('refuses card_on_delivery for a city whose rule does not take it', async () => {
    const error = await createOrder(order('რუსთავი', 'card_on_delivery')).catch((e) => e);

    expect(error.name).toBe('ValidationError');
    expect(error.status).toBe(400);
    expect(error.details.code).toBe('PAYMENT_METHOD_UNAVAILABLE');
  });

  it('accepts card_on_delivery where the rule takes it', async () => {
    const placed = await createOrder(order('თბილისი', 'card_on_delivery'));

    expect(placed.paymentMethod).toBe('card_on_delivery');
  });

  it('still accepts cash in a city that does not take the card', async () => {
    const placed = await createOrder(order('რუსთავი', 'cash'));

    expect(placed.paymentMethod).toBe('cash');
  });
});
