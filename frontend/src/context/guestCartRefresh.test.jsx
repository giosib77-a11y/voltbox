/**
 * The reducer half of the guest cart refresh: a line added again takes the
 * product page's fresh snapshot, and REFRESH reconciles lines with a quote.
 */

import { describe, expect, it } from 'vitest';

import { CART_ACTIONS, cartReducer, reconcileWithQuote } from './CartContext.jsx';

const product = (price, stock = 10) => ({
  id: 'p1',
  name: 'Phone',
  slug: 'phone',
  images: ['/new.png'],
  price,
  oldPrice: price + 100,
  stock,
});

const line = (qty, price, stock = 10) => ({
  productId: 'p1',
  qty,
  snapshot: { name: 'Old name', slug: 'phone', image: '/old.png', price, oldPrice: null, stock },
});

describe('ADD on a line already in the cart', () => {
  it("refreshes the line's snapshot from the product passed in, not only its quantity", () => {
    const state = { items: [line(1, 999)], hydrated: true };

    const next = cartReducer(state, {
      type: CART_ACTIONS.ADD,
      payload: { product: product(1099, 4), qty: 1 },
    });

    expect(next.items).toHaveLength(1);
    expect(next.items[0].qty).toBe(2);
    expect(next.items[0].snapshot).toEqual({
      name: 'Phone',
      slug: 'phone',
      image: '/new.png',
      price: 1099,
      oldPrice: 1199,
      stock: 4,
    });
  });
});

describe('reconcileWithQuote', () => {
  const quote = (qty, price, stock) => [
    {
      productId: 'p1',
      qty,
      snapshot: { name: 'Phone', slug: 'phone', image: '', price, oldPrice: null, stock },
    },
  ];

  it('replaces snapshots and reports a price change', () => {
    const { items, change } = reconcileWithQuote([line(1, 999)], quote(1, '1099.00', 10));
    expect(items[0].snapshot.price).toBe(1099);
    expect(change).toBe('prices');
  });

  it('clamps to the new stock and reports it', () => {
    const { items, change } = reconcileWithQuote([line(5, 999)], quote(5, '999.00', 2));
    expect(items[0].qty).toBe(2);
    expect(change).toBe('reduced');
  });

  it('removes absent lines and stock-0 lines, and reports removal over everything else', () => {
    expect(reconcileWithQuote([line(1, 999)], []).items).toEqual([]);
    const zero = reconcileWithQuote([line(1, 999)], quote(1, '1099.00', 0));
    expect(zero.items).toEqual([]);
    expect(zero.change).toBe('removed');
  });

  it('reports nothing when only the stock moved', () => {
    expect(reconcileWithQuote([line(1, 999, 10)], quote(1, '999.00', 7)).change).toBeNull();
  });
});

describe('REFRESH', () => {
  it('keeps the same state object when the quote changes nothing', () => {
    const state = { items: [line(1, 999)], hydrated: true };
    const next = cartReducer(state, {
      type: CART_ACTIONS.REFRESH,
      payload: [
        {
          productId: 'p1',
          qty: 1,
          snapshot: { name: 'Old name', slug: 'phone', image: '/old.png', price: '999', oldPrice: null, stock: '10' },
        },
      ],
    });
    expect(next).toBe(state);
  });

  it('never marks the cart as the account supplied it', () => {
    const state = { items: [line(1, 999)], hydrated: true };
    const next = cartReducer(state, { type: CART_ACTIONS.REFRESH, payload: [] });
    expect(next.accountItems).toBeUndefined();
  });
});
