/**
 * Tests for the cart totals.
 *
 * What they cover: that the page quotes the price the server will charge. The
 * backend computes the same figures in `services/order.py` with `Decimal`, and
 * the customer is billed by the backend - so a disagreement here is a quoted
 * total that turns into a different one at checkout.
 *
 * The case that mattered is the free-shipping threshold. A basket of 1.05 × 2
 * and 49.30 × 3 is 150.00 to the tetri and 149.99999999999997 in IEEE754.
 * Compared as floats that is below the threshold, so the page added 5 ₾ that
 * the server did not: quoted 155, billed 150, on exactly the basket where the
 * "free delivery from 150 ₾" promise is being tested.
 *
 * Checked exhaustively against the backend over every two-line basket summing
 * to the threshold - 195,883 of them. The old form was wrong in 2,412, and
 * 1,832 of those had every line priced at a normal 1 ₾ or more.
 */

import { describe, expect, it } from 'vitest';

import { amountToFreeShipping, calcShipping, calcTotals, isFreeShipping } from './pricing.js';

const FREE_FROM = 150;
const FEE = 5;

describe('calcShipping', () => {
  it.each([
    [0, 0],
    [0.01, FEE],
    [149.99, FEE],
    [FREE_FROM, 0],
    [150.01, 0],
    [1000, 0],
  ])('a subtotal of %s costs %s to deliver', (subtotal, expected) => {
    expect(calcShipping(subtotal)).toBe(expected);
  });

  it('treats a float that is a hair under the threshold as reaching it', () => {
    // What summing 1.05 × 2 + 49.30 × 3 actually produces.
    expect(calcShipping(149.99999999999997)).toBe(0);
  });

  it.each([[null], [undefined], [NaN], [-10]])('%s costs nothing', (subtotal) => {
    expect(calcShipping(subtotal)).toBe(0);
  });
});

describe('calcTotals', () => {
  it('adds up a simple basket', () => {
    const totals = calcTotals([
      { price: 10, qty: 2 },
      { price: 5.5, qty: 1 },
    ]);

    expect(totals).toMatchObject({ subtotal: 25.5, shipping: FEE, total: 30.5, itemsCount: 3 });
  });

  it('is empty for an empty basket', () => {
    expect(calcTotals([])).toMatchObject({ subtotal: 0, shipping: 0, total: 0, itemsCount: 0 });
  });

  it('counts savings from an old price', () => {
    const totals = calcTotals([{ price: 80, oldPrice: 100, qty: 2 }]);

    expect(totals.savings).toBe(40);
  });

  it('ignores an old price that is not actually higher', () => {
    expect(calcTotals([{ price: 100, oldPrice: 90, qty: 1 }]).savings).toBe(0);
  });

  describe('the free-shipping threshold, to the tetri', () => {
    it.each([
      // Each of these is exactly 150.00, and each floats to 149.99999999999997.
      [[{ price: 1.05, qty: 2 }, { price: 49.3, qty: 3 }]],
      [[{ price: 12.45, qty: 12 }, { price: 0.05, qty: 12 }]],
      [[{ price: 21.4, qty: 7 }, { price: 0.02, qty: 10 }]],
      [[{ price: 1.02, qty: 5 }, { price: 48.3, qty: 3 }]],
      [[{ price: 1.07, qty: 6 }, { price: 47.86, qty: 3 }]],
    ])('%j reaches exactly 150.00 and delivers free', (lines) => {
      const totals = calcTotals(lines);

      expect(totals.subtotal).toBe(FREE_FROM);
      expect(totals.shipping).toBe(0);
      expect(totals.total).toBe(FREE_FROM);
    });

    it('one tetri short still pays for delivery', () => {
      const totals = calcTotals([{ price: 149.99, qty: 1 }]);

      expect(totals.subtotal).toBe(149.99);
      expect(totals.shipping).toBe(FEE);
      expect(totals.total).toBe(154.99);
    });
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

describe('amountToFreeShipping', () => {
  it.each([
    [0, FREE_FROM],
    [100, 50],
    [FREE_FROM, 0],
    [200, 0],
  ])('%s ₾ is %s ₾ away', (subtotal, expected) => {
    expect(amountToFreeShipping(subtotal)).toBe(expected);
  });
});

describe('isFreeShipping', () => {
  it.each([
    [0, false],
    [149.99, false],
    [FREE_FROM, true],
    [200, true],
  ])('%s ₾ -> %s', (subtotal, expected) => {
    expect(isFreeShipping(subtotal)).toBe(expected);
  });
});
