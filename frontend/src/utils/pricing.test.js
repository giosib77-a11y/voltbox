/**
 * Tests for the cart totals and the delivery quote.
 *
 * The rules are passed in as `GET /delivery` returns them; nothing here reads a
 * number of the frontend's own. RULES below is the owner's table written out -
 * Tbilisi 8, Rustavi 5, free from 50 - so these tests check the arithmetic,
 * and backend/tests/test_orders.py checks the same numbers against the server.
 *
 * The case that mattered is the threshold. A basket of 0.05 × 6 and 9.94 × 5 is
 * 50.00 to the tetri and 49.99999999999999 in IEEE754. Compared as floats, the
 * page would quote the fee on exactly the basket the server delivers free.
 */

import { describe, expect, it } from 'vitest';
import {
  amountToFreeDelivery,
  calcTotals,
  deliveryFee,
  orderAmounts,
  totalWithDelivery,
} from './pricing.js';

const RULES = {
  cities: [
    { name: 'თბილისი', fee: 8 },
    { name: 'რუსთავი', fee: 5 },
  ],
  freeFrom: 50,
};

describe('deliveryFee', () => {
  it.each([
    ['თბილისი', 40, 8],
    ['რუსთავი', 40, 5],
    ['თბილისი', 49.99, 8],
    ['რუსთავი', 49.99, 5],
    ['თბილისი', 50, 0],
    ['რუსთავი', 50, 0],
    ['თბილისი', 200, 0],
  ])('%s, %s ₾ of goods: %s ₾', (city, subtotal, expected) => {
    expect(deliveryFee(subtotal, RULES, city)).toBe(expected);
  });

  it('is unknown below the threshold until a city is chosen', () => {
    expect(deliveryFee(40, RULES, '')).toBeNull();
    expect(deliveryFee(40, RULES)).toBeNull();
  });

  it('is unknown for a city the shop does not deliver to', () => {
    expect(deliveryFee(40, RULES, 'ბათუმი')).toBeNull();
  });

  it('is free everywhere from the threshold, with or without a city', () => {
    expect(deliveryFee(50, RULES)).toBe(0);
  });

  it('says nothing before the rules have arrived', () => {
    expect(deliveryFee(40, null, 'თბილისი')).toBeNull();
    expect(deliveryFee(500, null, 'თბილისი')).toBeNull();
  });

  it('treats a float that is a hair under the threshold as reaching it', () => {
    expect(deliveryFee(49.99999999999999, RULES, 'თბილისი')).toBe(0);
  });
});

describe('the threshold, to the tetri', () => {
  it.each([
    [[{ price: 0.05, qty: 6 }, { price: 9.94, qty: 5 }]],
    [[{ price: 0.01, qty: 5 }, { price: 16.65, qty: 3 }]],
    [[{ price: 0.04, qty: 8 }, { price: 16.56, qty: 3 }]],
  ])('%j reaches exactly 50.00 and delivers free', (lines) => {
    const { subtotal } = calcTotals(lines);

    expect(subtotal).toBe(50);
    expect(deliveryFee(subtotal, RULES, 'თბილისი')).toBe(0);
    expect(totalWithDelivery(subtotal, 0)).toBe(50);
  });

  it('one tetri short still pays for delivery', () => {
    const { subtotal } = calcTotals([{ price: 49.99, qty: 1 }]);

    expect(deliveryFee(subtotal, RULES, 'თბილისი')).toBe(8);
    expect(totalWithDelivery(subtotal, 8)).toBe(57.99);
  });
});

describe('amountToFreeDelivery', () => {
  it.each([
    [0, 50],
    [40, 10],
    [49.99, 0.01],
    [50, 0],
    [200, 0],
  ])('%s ₾ is %s ₾ away', (subtotal, expected) => {
    expect(amountToFreeDelivery(subtotal, RULES)).toBe(expected);
  });

  it('promises nothing before the rules have arrived', () => {
    expect(amountToFreeDelivery(10, null)).toBe(0);
  });
});

describe('totalWithDelivery', () => {
  it('adds in whole tetri', () => {
    expect(totalWithDelivery(40.1, 8)).toBe(48.1);
    expect(totalWithDelivery(0.1 + 0.2, 5)).toBe(5.3);
  });

  it('is unknown while the fee is', () => {
    expect(totalWithDelivery(40, null)).toBeNull();
  });
});

describe('calcTotals', () => {
  it('adds up a simple basket', () => {
    const totals = calcTotals([
      { price: 10, qty: 2 },
      { price: 5.5, qty: 1 },
    ]);

    expect(totals).toEqual({ subtotal: 25.5, itemsCount: 3, savings: 0 });
  });

  it('is empty for an empty basket', () => {
    expect(calcTotals([])).toEqual({ subtotal: 0, itemsCount: 0, savings: 0 });
  });

  it('counts savings only where the old price is higher', () => {
    expect(calcTotals([{ price: 80, oldPrice: 100, qty: 2 }]).savings).toBe(40);
    expect(calcTotals([{ price: 100, oldPrice: 90, qty: 1 }]).savings).toBe(0);
  });

  it('does not accumulate float error over many lines', () => {
    const lines = Array.from({ length: 30 }, () => ({ price: 0.1, qty: 3 }));

    expect(calcTotals(lines).subtotal).toBe(9);
  });

  it('handles the prices that float arithmetic classically mangles', () => {
    expect(calcTotals([{ price: 10.1, qty: 3 }]).subtotal).toBe(30.3);
    expect(calcTotals([{ price: 0.1, qty: 3 }]).subtotal).toBe(0.3);
    expect(calcTotals([{ price: 0.07, qty: 3 }]).subtotal).toBe(0.21);
  });
});

describe('orderAmounts', () => {
  it('reads the strings the API sends as numbers, so a free delivery is 0', () => {
    expect(orderAmounts({ subtotal: '80.00', shipping: '0.00', total: '80.00' })).toEqual({
      subtotal: 80,
      shipping: 0,
      total: 80,
    });
  });

  it('keeps an order with no stored fee to its total', () => {
    expect(orderAmounts({ total: 80 })).toEqual({ subtotal: null, shipping: null, total: 80 });
  });
});
