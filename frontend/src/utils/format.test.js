/**
 * Tests for calcDiscountPercent.
 *
 * What they cover: that this agrees with the backend, which computes the same
 * percentage in `schemas/mappers.py` with `Decimal` and ROUND_HALF_UP.
 *
 * Two implementations of one rule drift, and this pair did. The cases below are
 * the ones where it showed: ratios that land exactly on a half percent, where
 * float arithmetic produces 14.499999999999998 for something that is 14.5 on
 * paper. `Math.round` then answers 14 while the backend answers 15.
 *
 * The storefront displays the server's `discountPercent`, so the disagreement
 * only ever reached mock mode - the demo. Which is the worst place to show a
 * customer a different number from the one the API would have sent.
 */

import { describe, expect, it } from 'vitest';

import { calcDiscountPercent, formatDiscount } from './format.js';

describe('calcDiscountPercent', () => {
  it.each([
    [2499, 2799, 11],
    [40, 50, 20],
    [1, 2, 50],
    [99.99, 199.99, 50],
    [0.5, 1, 50],
  ])('(%s, %s) is %s%%', (price, oldPrice, expected) => {
    expect(calcDiscountPercent(price, oldPrice)).toBe(expected);
  });

  it.each([
    [100, null],
    [100, undefined],
    [100, 0],
    [100, 100],
    [100, 90],
    [0, 100],
    [null, 100],
  ])('(%s, %s) has no discount to show', (price, oldPrice) => {
    expect(calcDiscountPercent(price, oldPrice)).toBe(0);
  });

  describe('the exact half percent, where the two implementations disagreed', () => {
    /**
     * Each pair divides to a whole-and-a-half percent. The third value is what
     * the backend returns - `Decimal` with ROUND_HALF_UP, so always up.
     */
    it.each([
      [171, 200, 15], // 29/200 -> 14.5
      [342, 400, 15],
      [855, 1000, 15],
      [1710, 2000, 15],
      [42.75, 50, 15],
      [19.3, 20, 4], // 0.7/20 -> 3.5
      [19.1, 20, 5],
      [18.3, 20, 9],
      [18.1, 20, 10],
      [17.3, 20, 14],
    ])('(%s, %s) rounds up to %s%%, as the backend does', (price, oldPrice, expected) => {
      expect(calcDiscountPercent(price, oldPrice)).toBe(expected);
    });

    it('shows what the naive form would have answered', () => {
      // Kept as a statement of the bug rather than a description of it: this is
      // the expression that was here, and it is wrong by one.
      const naive = Math.round(((200 - 171) / 200) * 100);

      expect(naive).toBe(14);
      expect(calcDiscountPercent(171, 200)).toBe(15);
    });
  });
});

describe('formatDiscount', () => {
  it.each([
    [11, '-11%'],
    [0, '-0%'],
    [50, '-50%'],
  ])('%s renders as %s', (percent, expected) => {
    expect(formatDiscount(percent)).toBe(expected);
  });
});
