/**
 * A-126: on a phone the checkout overflowed the screen when the basket held a
 * product with a long name.
 *
 * Below `lg` the page grids are one implicit `auto` column and their children
 * default to `min-width: auto`, so the nowrap name widened the column and the
 * line's `truncate` never applied. jsdom has no layout, so these tests pin the
 * structure that prevents it: every grid child carries `min-w-0`, the name sits
 * in a `min-w-0` flex child and is truncated or clamped, and the price keeps
 * `shrink-0` and its full text. The real measurement (scrollWidth - innerWidth
 * at 360 and 390) is a browser check.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';

vi.mock('virtual:api-impl', () => import('../services/httpApi.js'));

let cartValue;
vi.mock('../hooks/useCart.js', () => ({ useCart: () => cartValue }));
vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({ user: null, isAuthenticated: false }),
}));
vi.mock('../hooks/useGuestCartQuote.js', () => ({ useGuestCartQuote: () => {} }));
vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

import Checkout from './Checkout.jsx';
import Cart from './Cart.jsx';
import OrderDetail from '../admin/pages/OrderDetail.jsx';
import * as adminApi from '../admin/adminApi.js';
import { forgetDeliveryRules, loadDeliveryRules } from '../hooks/useDeliveryRules.js';
import { formatPrice } from '../utils/format.js';

const LONG_NAME = 'Anker PowerLine III USB-C — USB-C კაბელი 2მ ძალიან გრძელი სახელი';

const item = {
  productId: 'p1',
  qty: 2,
  snapshot: { name: LONG_NAME, slug: 'anker', image: '/a.png', price: 64.95, stock: 10 },
};

const classes = (el) => (el.getAttribute('class') || '').split(/\s+/);

function expectAllMinW0(parent) {
  expect(parent.children.length).toBeGreaterThan(0);
  for (const child of parent.children) expect(classes(child)).toContain('min-w-0');
}

beforeEach(() => {
  vi.restoreAllMocks();
  forgetDeliveryRules();
  cartValue = {
    items: [item],
    itemsCount: 2,
    subtotal: 129.9,
    savings: 0,
    clear: vi.fn(),
    setQty: vi.fn(),
    removeItem: vi.fn(),
    restoreItem: vi.fn(),
    refreshFromQuote: vi.fn(async () => null),
  };
  global.fetch = vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      cities: [{ name: 'თბილისი', fee: '11.00', cardOnDelivery: true }],
      freeFrom: '100.00',
      currency: 'GEL',
      features: { email: false },
    }),
  }));
});

async function rulesLoaded() {
  await act(async () => {
    await loadDeliveryRules().catch(() => {});
  });
}

describe('checkout with a long product name', () => {
  it('lets the form grid shrink below the name, and truncates the name beside a fixed price', async () => {
    render(
      <MemoryRouter>
        <Checkout />
      </MemoryRouter>,
    );
    await rulesLoaded();

    const form = document.querySelector('form');
    expectAllMinW0(form);

    const name = screen.getByText(LONG_NAME);
    expect(classes(name)).toContain('truncate');
    expect(classes(name.parentElement)).toContain('min-w-0');

    const price = screen.getAllByText(formatPrice(64.95 * 2)).find((el) => el.closest('li'));
    expect(classes(price)).toContain('shrink-0');
  });
});

describe('cart with a long product name', () => {
  it('lets the cart grid shrink, clamps the name and shows the whole line total', async () => {
    render(
      <MemoryRouter>
        <Cart />
      </MemoryRouter>,
    );
    await rulesLoaded();

    const name = screen.getByText(LONG_NAME, { selector: 'a' });
    // li -> ul -> bordered card -> grid
    const grid = name.closest('ul').parentElement.parentElement;
    expectAllMinW0(grid);

    expect(classes(name).some((c) => c.startsWith('line-clamp-2'))).toBe(true);
    expect(classes(name.parentElement)).toContain('min-w-0');

    expect(screen.getAllByText(formatPrice(64.95 * 2)).length).toBeGreaterThan(0);
  });
});

describe('admin order detail with a long product name', () => {
  it('lets the grid shrink, truncates the name and keeps the line total fixed', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue({
      id: 'o-1',
      orderNumber: 'VB-1001',
      status: 'pending',
      createdAt: '2026-10-01T10:00:00Z',
      deletedAt: null,
      purgeAt: null,
      allowedTransitions: ['confirmed'],
      customerName: 'ნინო',
      phone: '555',
      email: null,
      city: 'თბილისი',
      customer: { address: 'რუსთაველი 1' },
      notes: null,
      paymentMethod: 'cash',
      subtotal: '129.90',
      shipping: '11.00',
      total: '140.90',
      items: [
        { id: 'i1', productName: LONG_NAME, imageUrl: null, unitPrice: '64.95', quantity: 2, lineTotal: '129.90' },
      ],
      history: [],
    });
    render(
      <MemoryRouter initialEntries={['/admin/orders/o-1']}>
        <Routes>
          <Route path="/admin/orders/:id" element={<OrderDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    const name = await screen.findByText(LONG_NAME);
    expect(classes(name)).toContain('truncate');
    expect(classes(name.parentElement)).toContain('min-w-0');

    const row = name.closest('li');
    const total = [...row.querySelectorAll('span')].find((el) => /129[.,]90/.test(el.textContent));
    expect(classes(total)).toContain('shrink-0');

    const grid = row.closest('section').parentElement.parentElement;
    expectAllMinW0(grid);
  });
});
