/**
 * Tests for CartAccountSync.
 *
 * What they cover: the two moments the cart stops being only this browser's -
 * signing in, when a basket here has to be reconciled with one saved on the
 * account, and signing out, when it has to stop being on screen.
 *
 * What signing out does is the part worth stating, because it is conditional.
 * It empties the basket only when a save has come back, which is what makes
 * emptying putting it away rather than losing it; on a shared computer that is
 * what stops the next person seeing what the last one was about to buy. When
 * the account never confirmed it, the basket stays and says so.
 *
 * The mock replaces the implementation behind `services/api.js`, not api.js
 * itself. api.js re-exports each function by hand, and from the day this sync
 * was written it did not re-export these three: CartContext called `undefined`,
 * the error went into an empty catch, and nothing reached the account. These
 * tests mocked api.js and so replaced the one layer that was broken. Mocked a
 * layer lower, the calls go through the real api.js and every test here fails
 * if it drops one again.
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
import { ToastProvider } from './ToastContext.jsx';
import ToastViewport from '../components/common/Toast.jsx';
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

/**
 * The tree as main.jsx nests it. The viewport is what puts a message on screen;
 * ToastProvider on its own only queues it.
 */
const tree = (children = <Harness />) => (
  <ToastProvider>
    <CartProvider>
      <CartAccountSync />
      {children}
    </CartProvider>
    <ToastViewport />
  </ToastProvider>
);

const renderSync = () => render(tree());

/** What sign-out says when the account never confirmed it has the basket. */
const KEPT = 'კალათა ამ ბრაუზერში დარჩა — ანგარიშზე შენახვა ვერ მოხერხდა';

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
    rerender(tree());

    expect(api.mergeCart).toHaveBeenCalledTimes(1);
  });

  it('merges again when a different account signs in', async () => {
    authValue = { user: { id: 'u1' }, initializing: false };
    const { rerender } = renderSync();
    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(1));

    authValue = { user: { id: 'u2' }, initializing: false };
    rerender(tree());

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
    // Waiting for the save rather than for the item to appear: a save that has
    // come back is the whole condition for emptying anything.
    await waitFor(
      () =>
        expect(api.saveCart).toHaveBeenLastCalledWith([
          expect.objectContaining({ productId: 'p1' }),
        ]),
      { timeout: 2000 },
    );
    await api.saveCart.mock.results.at(-1).value;

    authValue = { user: null, initializing: false };
    rerender(tree());

    // Saved on the account first, so this is putting it away rather than
    // losing it - and the next person on a shared computer sees nothing.
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('0'));
    expect(screen.queryByText(KEPT)).not.toBeInTheDocument();
  });

  it('keeps the basket when the merge failed, instead of emptying one nothing holds', async () => {
    // The failure this is really about is not a 500: it is 1ebe26b, where the
    // call was undefined and the TypeError went into an empty catch. Signing
    // out then emptied a basket that had never been anywhere.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    api.mergeCart.mockRejectedValueOnce(new Error('the server is not there'));
    authValue = { user: { id: 'u1' }, initializing: false };
    const { rerender } = renderSync();
    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(1));
    // Said somewhere, which is exactly what the empty catch did not do.
    await waitFor(() =>
      expect(warn).toHaveBeenCalledWith(expect.stringContaining('mergeCart'), expect.any(Error)),
    );

    screen.getByText('add').click();
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'));
    // Saving stays off after a failed merge: PUT /cart replaces, and this
    // browser has not read what it would be replacing.
    expect(api.saveCart).not.toHaveBeenCalled();

    authValue = { user: null, initializing: false };
    rerender(tree());

    expect(await screen.findByText(KEPT)).toBeInTheDocument();
    expect(screen.getByTestId('count')).toHaveTextContent('1');
  });

  it('keeps the basket when a save failed, however well the merge went', async () => {
    authValue = { user: { id: 'u1' }, initializing: false };
    const { rerender } = renderSync();
    await waitFor(() => expect(api.mergeCart).toHaveBeenCalledTimes(1));

    // Let the save that follows the merge land first, so the account is known
    // to hold the basket and the failure below is what takes that back.
    await waitFor(() => expect(api.saveCart).toHaveBeenCalledTimes(1), { timeout: 2000 });
    await api.saveCart.mock.results[0].value;

    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    api.saveCart.mockRejectedValueOnce(new Error('the server is not there'));
    screen.getByText('add').click();
    await waitFor(() => expect(api.saveCart).toHaveBeenCalledTimes(2), { timeout: 2000 });
    await expect(api.saveCart.mock.results[1].value).rejects.toThrow();
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('saveCart'), expect.any(Error));

    authValue = { user: null, initializing: false };
    rerender(tree());

    // The account holds the basket as it was before this item, so emptying
    // would lose the item and say nothing about it.
    expect(await screen.findByText(KEPT)).toBeInTheDocument();
    expect(screen.getByTestId('count')).toHaveTextContent('1');
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

  const renderClear = () => render(tree(<ClearHarness />));

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
