/**
 * Tests for CartAccountSync.
 *
 * What they cover: the two moments the cart stops being only this browser's -
 * signing in, when a basket here has to be reconciled with one saved on the
 * account, and signing out, when it has to stop being on screen.
 *
 * Signing out clearing the cart is the part worth stating. It is safe only
 * because the cart is saved on the account first: without that, emptying it
 * would be losing it. With it, leaving the basket on screen would show the next
 * person on a shared computer what the last one was about to buy.
 *
 * The mock replaces the implementation behind `services/api.js`, not api.js
 * itself. api.js re-exports each function by hand, and from the day this sync
 * was written it did not re-export these three: CartContext called
 * `undefined`, the error was swallowed, and nothing reached the account. These tests mocked api.js and
 * so replaced the one layer that was broken. Mocked a layer lower, the calls
 * go through the real api.js and every test here fails if it drops one again.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('virtual:api-impl', async (importOriginal) => ({
  ...(await importOriginal()),
  mergeCart: vi.fn(async (items) => items.map((i) => ({ ...i, snapshot: { ...i.snapshot } }))),
  saveCart: vi.fn(async (items) => items),
  clearCart: vi.fn(async () => {}),
}));

import * as api from 'virtual:api-impl';
import CartAccountSync from './CartAccountSync.jsx';
import { CartProvider } from './CartContext.jsx';
import { useCart } from '../hooks/useCart.js';

/** A stand-in for AuthProvider whose value the test drives directly. */
let authValue = { user: null, initializing: true };
vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => authValue,
}));

const PRODUCT = {
  id: 'p1',
  name: 'Cable',
  slug: 'cable',
  images: ['/a.png'],
  price: 10,
  oldPrice: null,
  stock: 5,
};

function Harness() {
  const { items, addItem } = useCart();
  return (
    <>
      <button type="button" onClick={() => addItem(PRODUCT, 2)}>
        add
      </button>
      <span data-testid="count">{items.length}</span>
      <span data-testid="qty">{items[0]?.qty ?? 0}</span>
    </>
  );
}

const renderSync = () =>
  render(
    <CartProvider>
      <CartAccountSync />
      <Harness />
    </CartProvider>,
  );

beforeEach(() => {
  localStorage.clear();
  authValue = { user: null, initializing: true };
  vi.clearAllMocks();
});

describe('CartAccountSync', () => {
  it('does nothing at all while the session is still unknown', async () => {
    renderSync();

    await waitFor(() => expect(screen.getByTestId('count')).toBeInTheDocument());
    expect(api.mergeCart).not.toHaveBeenCalled();
  });

  it('does not merge for a guest', async () => {
    authValue = { user: null, initializing: false };
    renderSync();

    await waitFor(() => expect(screen.getByTestId('count')).toBeInTheDocument());
    expect(api.mergeCart).not.toHaveBeenCalled();
  });

  it('merges once when somebody signs in', async () => {
    authValue = { user: { id: 'u1' }, initializing: false };
    renderSync();

    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(1));
  });

  it('does not merge again when the same user is simply re-read', async () => {
    // A refresh and a profile edit both produce a new user object. Neither is
    // a sign-in, and merging on each would be a request per refresh.
    authValue = { user: { id: 'u1' }, initializing: false };
    const { rerender } = renderSync();
    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(1));

    authValue = { user: { id: 'u1', firstName: 'changed' }, initializing: false };
    rerender(
      <CartProvider>
        <CartAccountSync />
        <Harness />
      </CartProvider>,
    );

    expect(api.mergeCart).toHaveBeenCalledTimes(1);
  });

  it('merges again when a different account signs in', async () => {
    authValue = { user: { id: 'u1' }, initializing: false };
    const { rerender } = renderSync();
    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(1));

    authValue = { user: { id: 'u2' }, initializing: false };
    rerender(
      <CartProvider>
        <CartAccountSync />
        <Harness />
      </CartProvider>,
    );

    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(2));
  });

  it('saves what is added after signing in to the account', async () => {
    authValue = { user: { id: 'u1' }, initializing: false };
    renderSync();
    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(1));

    screen.getByText('add').click();

    // After the debounce, so allow for it rather than faking the clock.
    await waitFor(
      () =>
        expect(api.saveCart).toHaveBeenLastCalledWith([
          expect.objectContaining({ productId: 'p1', qty: 2 }),
        ]),
      { timeout: 2000 },
    );
  });

  it('empties the cart on this browser when they sign out', async () => {
    authValue = { user: { id: 'u1' }, initializing: false };
    const { rerender } = renderSync();
    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(1));

    screen.getByText('add').click();
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'));

    authValue = { user: null, initializing: false };
    rerender(
      <CartProvider>
        <CartAccountSync />
        <Harness />
      </CartProvider>,
    );

    // Saved on the account first, so this is putting it away rather than
    // losing it - and the next person on a shared computer sees nothing.
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('0'));
  });
});

describe('emptying the cart', () => {
  function ClearHarness() {
    const { addItem, clear, items } = useCart();
    return (
      <>
        <button type="button" onClick={() => addItem(PRODUCT, 1)}>
          add
        </button>
        <button type="button" onClick={clear}>
          clear
        </button>
        <span data-testid="count">{items.length}</span>
      </>
    );
  }

  const renderClear = () =>
    render(
      <CartProvider>
        <CartAccountSync />
        <ClearHarness />
      </CartProvider>,
    );

  it('tells the account at once rather than waiting for the debounce', async () => {
    // Placing an order and emptying by hand are both followed by leaving. A tab
    // closed a moment later would otherwise leave the account holding items
    // that were just bought.
    authValue = { user: { id: 'u1' }, initializing: false };
    renderClear();
    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(1));

    screen.getByText('add').click();
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'));

    screen.getByText('clear').click();

    await waitFor(() => expect(api.clearCart).toHaveBeenCalledTimes(1));
  });

  it('does not call the API for a guest', async () => {
    authValue = { user: null, initializing: false };
    renderClear();

    screen.getByText('add').click();
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'));
    screen.getByText('clear').click();

    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('0'));
    expect(api.clearCart).not.toHaveBeenCalled();
  });
});
