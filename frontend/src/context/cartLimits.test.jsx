/**
 * The cart holds no more than checkout takes: 20 different products, 10 units
 * of each (the owner's rule of 2026-10-10, backend/app/core/limits.py).
 *
 * The reducer is where the numbers are enforced, and a cart read back from
 * localStorage goes through it too, so a basket saved before the cap is cut
 * down on load instead of failing at checkout.
 */

import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { CART_ACTIONS, cartLimitHit, cartReducer } from './CartContext.jsx';
import QuantityStepper from '../components/cart/QuantityStepper.jsx';
import { MAX_CART_LINES, MAX_LINE_QTY } from '../constants/index.js';
import { cartLimitMessage } from '../utils/cartLimit.js';

const product = (n, stock = 500) => ({
  id: `p${n}`,
  name: `Product ${n}`,
  slug: `p-${n}`,
  images: [],
  price: 10,
  stock,
});

const line = (n, qty = 1, stock = 500) => ({
  productId: `p${n}`,
  qty,
  snapshot: { name: `Product ${n}`, slug: `p-${n}`, image: '', price: 10, oldPrice: null, stock },
});

const add = (state, p, qty = 1) => cartReducer(state, { type: CART_ACTIONS.ADD, payload: { product: p, qty } });

const fullCart = () => ({
  items: Array.from({ length: MAX_CART_LINES }, (_, n) => line(n)),
  hydrated: true,
});

describe('the numbers', () => {
  it('are the owner\'s: 20 products, 10 units each', () => {
    expect(MAX_CART_LINES).toBe(20);
    expect(MAX_LINE_QTY).toBe(10);
  });
});

describe('cartReducer', () => {
  it('stops a line at 10 units however many are asked for and however large the stock', () => {
    const state = add({ items: [], hydrated: true }, product(1), 25);
    expect(state.items[0].qty).toBe(10);

    const more = add(state, product(1), 1);
    expect(more.items[0].qty).toBe(10);
  });

  it('SET_QTY past 10 settles on 10', () => {
    const state = cartReducer(
      { items: [line(1, 3)], hydrated: true },
      { type: CART_ACTIONS.SET_QTY, payload: { productId: 'p1', qty: 40 } },
    );
    expect(state.items[0].qty).toBe(10);
  });

  it('still honours a stock below the cap', () => {
    const state = add({ items: [], hydrated: true }, product(1, 3), 8);
    expect(state.items[0].qty).toBe(3);
  });

  it('refuses a 21st product but still lets a product in the cart grow', () => {
    const full = fullCart();

    expect(add(full, product(99)).items).toHaveLength(20);
    expect(add(full, product(99)).items.some((i) => i.productId === 'p99')).toBe(false);
    expect(add(full, product(0), 2).items[0].qty).toBe(3);
  });

  it('cuts a stored cart past either limit down on load', () => {
    const stored = [
      ...Array.from({ length: 25 }, (_, n) => line(n, 1)),
    ];
    stored[0] = line(0, 99);

    const state = cartReducer({ items: [], hydrated: false }, { type: CART_ACTIONS.HYDRATE, payload: stored });

    expect(state.items).toHaveLength(20);
    expect(state.items[0].qty).toBe(10);
    expect(state.items.at(-1).productId).toBe('p19');
  });
});

describe('cartLimitHit', () => {
  it('names the limit an add would run into', () => {
    expect(cartLimitHit(fullCart().items, 'p99', 1)).toBe('lines');
    expect(cartLimitHit([line(1, 10)], 'p1', 1)).toBe('qty');
    expect(cartLimitHit([line(1, 8)], 'p1', 3)).toBe('qty');
    expect(cartLimitHit([line(1, 9)], 'p1', 1)).toBeNull();
    expect(cartLimitHit([], 'p1', 1)).toBeNull();
  });
});

describe('QuantityStepper', () => {
  it('does not offer more than 10 even when asked for more', () => {
    render(<QuantityStepper value={10} max={500} onChange={() => {}} />);

    expect(screen.getByRole('button', { name: /გაზრდა|Increase/ }).disabled).toBe(true);
    expect(screen.getByRole('spinbutton').max).toBe('10');
  });

  it('clamps a typed number to 10', () => {
    const seen = [];
    render(<QuantityStepper value={2} max={500} onChange={(n) => seen.push(n)} />);

    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '55' } });

    expect(seen).toEqual([10]);
  });
});

describe('the explanation', () => {
  it('says the number for each limit, from the translation files', () => {
    expect(cartLimitMessage('lines')).toContain('20');
    expect(cartLimitMessage('qty')).toContain('10');
    expect(cartLimitMessage('lines')).not.toBe(cartLimitMessage('qty'));
  });
});
