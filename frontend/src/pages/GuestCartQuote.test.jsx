/**
 * Tests for the guest cart's refresh against POST /cart/quote.
 *
 * A guest's basket is a snapshot taken when each product was added, and
 * nothing used to refresh it: checkout showed Monday's price while the server
 * (correctly) charged Wednesday's. These tests run the real CartProvider and
 * the real api.js over httpApi with only `fetch` replaced, so they fail if the
 * quote is not sent, not applied, or applied to a signed-in cart.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect, useRef } from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

vi.mock('virtual:api-impl', () => import('../services/httpApi.js'));

let authValue;
vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => authValue,
}));

import Checkout from './Checkout.jsx';
import Cart from './Cart.jsx';
import { CartProvider, useCartContext } from '../context/CartContext.jsx';
import { ToastProvider } from '../context/ToastContext.jsx';
import ToastViewport from '../components/common/Toast.jsx';
import { forgetDeliveryRules } from '../hooks/useDeliveryRules.js';
import { STORAGE_KEYS } from '../constants/index.js';

const GUEST = { user: null, isAuthenticated: false, initializing: false };
const SIGNED_IN = { user: { id: 'u1' }, isAuthenticated: true, initializing: false };

const DELIVERY = {
  cities: [{ name: 'თბილისი', fee: '8.00' }],
  freeFrom: '50.00',
  currency: 'GEL',
  features: { email: false },
};

const reply = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

const line = (productId, qty, price, stock = 10, name = `Product ${productId}`) => ({
  productId,
  qty,
  snapshot: { name, slug: productId, image: '', price, oldPrice: null, stock },
});

/** A line as POST /cart/quote answers: money as strings. */
const quoted = (productId, qty, price, stock = 10, name = `Product ${productId}`) => ({
  productId,
  qty,
  snapshot: { name, slug: productId, image: '', price, oldPrice: null, stock },
});

const MSG_PRICES = 'კალათაში ფასები განახლდა — ქვემოთ მიმდინარე ჯამია';
const MSG_REMOVED = 'ზოგი პროდუქტი აღარ არის ხელმისაწვდომი და კალათიდან ამოვიღეთ';
const MSG_REDUCED = 'რაოდენობა მარაგში არსებულამდე შევამცირეთ';

let quoteReply;
let fetchMock;

function seedCart(items) {
  localStorage.setItem(STORAGE_KEYS.cart, JSON.stringify(items));
}

function renderPage(Page) {
  return render(
    <ToastProvider>
      <CartProvider>
        <MemoryRouter>
          <Page />
        </MemoryRouter>
      </CartProvider>
      <ToastViewport />
    </ToastProvider>,
  );
}

const quoteCalls = () => fetchMock.mock.calls.filter(([url]) => String(url).includes('/cart/quote'));

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  forgetDeliveryRules();
  authValue = GUEST;
  quoteReply = () => reply({ items: [] });
  fetchMock = vi.fn(async (url) => {
    if (String(url).endsWith('/delivery')) return reply(DELIVERY);
    if (String(url).includes('/cart/quote')) return quoteReply();
    throw new Error(`unexpected request ${url}`);
  });
  global.fetch = fetchMock;
});

describe('a guest opening checkout', () => {
  it('sees the price the server will charge, and is told it changed', async () => {
    seedCart([line('p1', 1, 999, 10, 'Phone')]);
    quoteReply = () => reply({ items: [quoted('p1', 1, '1099.00', 10, 'Phone')] });
    renderPage(Checkout);

    expect(await screen.findByText(MSG_PRICES)).toBeInTheDocument();
    // The line and the summary both carry the fresh price; the stale one is gone.
    expect(screen.getAllByText('1 099 ₾').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('999 ₾')).not.toBeInTheDocument();
  });

  it('gets free delivery when the new price crosses the line upwards', async () => {
    seedCart([line('p1', 1, 40)]);
    quoteReply = () => reply({ items: [quoted('p1', 1, '60.00')] });
    renderPage(Checkout);

    expect(await screen.findByText(MSG_PRICES)).toBeInTheDocument();
    expect(await screen.findByText('უფასო')).toBeInTheDocument();
    expect(screen.queryByText(/დაამატე კიდევ/)).not.toBeInTheDocument();
  });

  it('loses free delivery when the new price crosses the line downwards', async () => {
    seedCart([line('p1', 1, 60)]);
    quoteReply = () => reply({ items: [quoted('p1', 1, '40.00')] });
    renderPage(Checkout);

    expect(await screen.findByText(MSG_PRICES)).toBeInTheDocument();
    // 50 - 40: ten lari short of free delivery, which the stale 60 hid.
    expect(await screen.findByText('10 ₾')).toBeInTheDocument();
    expect(screen.queryByText('უფასო')).not.toBeInTheDocument();
  });

  it('drops a line the quote does not return, and says so', async () => {
    seedCart([line('p1', 1, 20, 10, 'Kept'), line('p2', 1, 30, 10, 'Archived')]);
    quoteReply = () => reply({ items: [quoted('p1', 1, '20.00', 10, 'Kept')] });
    renderPage(Checkout);

    expect(await screen.findByText(MSG_REMOVED)).toBeInTheDocument();
    expect(screen.getByText('Kept')).toBeInTheDocument();
    expect(screen.queryByText('Archived')).not.toBeInTheDocument();
    // Prices did not change, so the removal is the only message.
    expect(screen.queryByText(MSG_PRICES)).not.toBeInTheDocument();
  });

  it('drops a line whose stock is now zero: the server refuses it', async () => {
    seedCart([line('p1', 2, 20, 10, 'Sold out')]);
    quoteReply = () => reply({ items: [quoted('p1', 2, '20.00', 0, 'Sold out')] });
    renderPage(Checkout);

    expect(await screen.findByText(MSG_REMOVED)).toBeInTheDocument();
    expect(screen.queryByText('Sold out')).not.toBeInTheDocument();
  });

  it('reduces a quantity above the new stock', async () => {
    seedCart([line('p1', 5, 20, 10, 'Cable')]);
    quoteReply = () => reply({ items: [quoted('p1', 5, '20.00', 2, 'Cable')] });
    renderPage(Checkout);

    expect(await screen.findByText(MSG_REDUCED)).toBeInTheDocument();
    expect(screen.getByText('2 × 20 ₾')).toBeInTheDocument();
    // Written by CartContext's localStorage effect, which can land after the
    // toast's render on a loaded machine (the full suite failed here once).
    await waitFor(() => expect(JSON.parse(localStorage.getItem(STORAGE_KEYS.cart))[0].qty).toBe(2));
  });

  it('shows one message when several things changed', async () => {
    seedCart([line('p1', 1, 20, 10, 'A'), line('p2', 1, 30, 10, 'B')]);
    quoteReply = () => reply({ items: [quoted('p1', 1, '25.00', 10, 'A')] });
    renderPage(Checkout);

    expect(await screen.findByText(MSG_REMOVED)).toBeInTheDocument();
    expect(screen.queryByText(MSG_PRICES)).not.toBeInTheDocument();
  });

  it('keeps the cart and stays usable when the quote fails', async () => {
    seedCart([line('p1', 1, 999, 10, 'Phone')]);
    quoteReply = () => reply({ error: { message: 'slow down' } }, 429);
    renderPage(Checkout);

    await waitFor(() => expect(quoteCalls()).toHaveLength(1));
    expect(await screen.findByRole('button', { name: 'შეკვეთის დადასტურება' })).toBeInTheDocument();
    expect(screen.getAllByText('999 ₾').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(MSG_PRICES)).not.toBeInTheDocument();
    expect(screen.queryByText(MSG_REMOVED)).not.toBeInTheDocument();
  });

  it('keeps the cart when the network is down', async () => {
    seedCart([line('p1', 1, 999, 10, 'Phone')]);
    quoteReply = () => {
      throw new TypeError('Failed to fetch');
    };
    renderPage(Checkout);

    await waitFor(() => expect(quoteCalls()).toHaveLength(1));
    expect(screen.getAllByText('999 ₾').length).toBeGreaterThanOrEqual(2);
  });

  it('asks once, and says nothing when nothing changed', async () => {
    seedCart([line('p1', 1, 20)]);
    quoteReply = () => reply({ items: [quoted('p1', 1, '20.00')] });
    renderPage(Checkout);

    await waitFor(() => expect(quoteCalls()).toHaveLength(1));
    await screen.findByText('Product p1');
    expect(screen.queryByText(MSG_PRICES)).not.toBeInTheDocument();
    expect(quoteCalls()).toHaveLength(1);
  });
});

describe('a guest opening the cart', () => {
  it('gets the same refresh', async () => {
    seedCart([line('p1', 1, 999, 10, 'Phone')]);
    quoteReply = () => reply({ items: [quoted('p1', 1, '1099.00', 10, 'Phone')] });
    renderPage(Cart);

    expect(await screen.findByText(MSG_PRICES)).toBeInTheDocument();
    expect(screen.queryByText('999 ₾')).not.toBeInTheDocument();
  });
});

describe('a guest who added a product through the page', () => {
  // The product as GET /products/:id sends it: money and stock as strings.
  const apiProduct = {
    id: 'p1',
    name: 'Phone',
    slug: 'phone',
    images: [],
    price: '999.00',
    oldPrice: null,
    stock: 10,
  };

  function AddOnce() {
    const { addItem, hydrated } = useCartContext();
    const done = useRef(false);
    useEffect(() => {
      if (!hydrated || done.current) return;
      done.current = true;
      addItem(apiProduct);
    }, [hydrated, addItem]);
    return null;
  }

  it('is not told the prices changed when the quote returns the same price', async () => {
    quoteReply = () => reply({ items: [quoted('p1', 1, '999.00', 10, 'Phone')] });
    render(
      <ToastProvider>
        <CartProvider>
          <AddOnce />
          <MemoryRouter>
            <Cart />
          </MemoryRouter>
        </CartProvider>
        <ToastViewport />
      </ToastProvider>,
    );

    await waitFor(() => expect(quoteCalls()).toHaveLength(1));
    // Let the answer be applied and the toast (if any) rendered before looking.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
    expect(screen.getByText('Phone')).toBeInTheDocument();
    expect(screen.queryByText(MSG_PRICES)).not.toBeInTheDocument();
  });
});

describe('a signed-in shopper', () => {
  it('does not call the quote: the account supplies the lines', async () => {
    authValue = SIGNED_IN;
    seedCart([line('p1', 1, 999)]);
    renderPage(Checkout);

    await screen.findByRole('button', { name: 'შეკვეთის დადასტურება' });
    expect(quoteCalls()).toHaveLength(0);
  });

  it('does not call it while the session is still being restored', async () => {
    authValue = { user: null, isAuthenticated: false, initializing: true };
    seedCart([line('p1', 1, 999)]);
    renderPage(Cart);

    await screen.findByText('Product p1');
    expect(quoteCalls()).toHaveLength(0);
  });
});
