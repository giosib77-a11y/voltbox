/**
 * Tests for the checkout form.
 *
 * This is the one screen where a basket becomes an order: it checks the
 * delivery details, sends them to POST /orders under an Idempotency-Key, and
 * only once the order exists empties the cart and moves on to the thank-you
 * page. What goes wrong here goes wrong in the count of orders - a failed
 * attempt that throws the basket away anyway, a retry that goes out under a new
 * key and becomes a second order, or an Enter press during a slow request that
 * sends the same order twice.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import Checkout from './Checkout.jsx';
import * as api from '../services/api.js';
import { ToastProvider } from '../context/ToastContext.jsx';
import ToastViewport from '../components/common/Toast.jsx';

let navigate;
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return { ...actual, useNavigate: () => navigate };
});

/** Stand-ins for CartProvider and AuthProvider whose values the test drives directly. */
let cartValue;
vi.mock('../hooks/useCart.js', () => ({
  useCart: () => cartValue,
}));
vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({ user: null, isAuthenticated: false }),
}));

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

const ITEMS = [
  {
    productId: 'p1',
    qty: 2,
    snapshot: { name: 'Cable', slug: 'cable', image: '/a.png', price: 40 },
  },
];

const cart = (items) => ({
  items,
  itemsCount: items.reduce((sum, item) => sum + item.qty, 0),
  subtotal: 80,
  shipping: 0,
  total: 80,
  savings: 0,
  clear: vi.fn(),
});

// ToastProvider only queues messages; the viewport is what puts them on screen.
const renderPage = () =>
  render(
    <ToastProvider>
      <MemoryRouter>
        <Checkout />
      </MemoryRouter>
      <ToastViewport />
    </ToastProvider>,
  );

const submitButton = () => screen.getByRole('button', { name: 'შეკვეთის დადასტურება' });

/** Fills every required field, with the padding and spacing a person actually types. */
function fillValidForm() {
  fireEvent.change(screen.getByLabelText(/^სახელი/), { target: { value: '  გიორგი ' } });
  fireEvent.change(screen.getByLabelText(/^გვარი/), { target: { value: ' ბერიძე  ' } });
  fireEvent.change(screen.getByLabelText(/^ტელეფონი/), { target: { value: '555 12 34 56' } });
  fireEvent.change(screen.getByLabelText(/^ქალაქი/), { target: { value: 'თბილისი' } });
  fireEvent.change(screen.getByLabelText(/^მისამართი/), { target: { value: 'ჭავჭავაძის 42' } });
}

beforeEach(() => {
  vi.restoreAllMocks();
  // The key hook keeps its attempt in sessionStorage; one test's key must not
  // become the next test's "retry".
  sessionStorage.clear();
  navigate = vi.fn();
  cartValue = cart(ITEMS);
});

describe('the checkout form', () => {
  it('shows an empty basket instead of a form nobody can submit', () => {
    cartValue = cart([]);
    renderPage();

    expect(screen.getByText('კალათა ცარიელია')).toBeInTheDocument();
    expect(screen.queryByLabelText(/^სახელი/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'შეკვეთის დადასტურება' })).not.toBeInTheDocument();
  });

  it('sends nothing for an incomplete form and takes the customer to the first gap', async () => {
    const createOrder = vi.spyOn(api, 'createOrder');
    renderPage();

    fireEvent.change(screen.getByLabelText(/^სახელი/), { target: { value: 'გიორგი' } });
    fireEvent.change(screen.getByLabelText(/^გვარი/), { target: { value: 'ბერიძე' } });
    fireEvent.click(submitButton());

    expect(await screen.findByText('შეავსეთ სავალდებულო ველები სწორად')).toBeInTheDocument();
    expect(createOrder).not.toHaveBeenCalled();
    // The first invalid field, not the first field: the names were filled in.
    expect(screen.getByLabelText(/^ტელეფონი/)).toHaveFocus();
    expect(screen.getByLabelText(/^ტელეფონი/)).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText(/^ქალაქი/)).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText(/^მისამართი/)).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText(/^სახელი/)).not.toHaveAttribute('aria-invalid');
  });

  it('sends the order once, with the details cleaned up and a key attached', async () => {
    const createOrder = vi
      .spyOn(api, 'createOrder')
      .mockResolvedValue({ orderNumber: 'VB-20260918-1000' });
    renderPage();

    fillValidForm();
    fireEvent.click(submitButton());

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(createOrder).toHaveBeenCalledTimes(1);
    expect(createOrder).toHaveBeenCalledWith({
      items: ITEMS,
      customer: {
        firstName: 'გიორგი',
        lastName: 'ბერიძე',
        phone: '555123456',
        city: 'თბილისი',
        address: 'ჭავჭავაძის 42',
        comment: '',
      },
      paymentMethod: 'cash',
      // POST /orders refuses a request without one (5a1089e).
      idempotencyKey: expect.stringMatching(UUID_V4),
    });
  });

  it('empties the cart and replaces checkout with the thank-you page once the order exists', async () => {
    vi.spyOn(api, 'createOrder').mockResolvedValue({ orderNumber: 'VB-20260918-1000' });
    renderPage();

    fillValidForm();
    fireEvent.click(submitButton());

    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith('/checkout/success/VB-20260918-1000', {
        replace: true,
      }),
    );
    expect(cartValue.clear).toHaveBeenCalledTimes(1);
  });

  it('keeps the basket and the key after a failure, so the retry cannot become a second order', async () => {
    const createOrder = vi
      .spyOn(api, 'createOrder')
      .mockRejectedValueOnce(new Error('სერვერთან კავშირი ვერ დამყარდა'))
      .mockResolvedValueOnce({ orderNumber: 'VB-20260918-1000' });
    renderPage();

    fillValidForm();
    fireEvent.click(submitButton());

    expect(await screen.findByText('სერვერთან კავშირი ვერ დამყარდა')).toBeInTheDocument();
    expect(cartValue.clear).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();

    // The request may have reached the server before it failed; the retry has
    // to be recognisable as the same order.
    await waitFor(() => expect(submitButton()).toBeEnabled());
    fireEvent.click(submitButton());
    await waitFor(() => expect(navigate).toHaveBeenCalled());

    expect(createOrder).toHaveBeenCalledTimes(2);
    const [first, retry] = createOrder.mock.calls.map(([payload]) => payload.idempotencyKey);
    expect(first).toMatch(UUID_V4);
    expect(retry).toBe(first);
  });

  it('ignores Enter while the first request is still on its way', async () => {
    let settle;
    const createOrder = vi.spyOn(api, 'createOrder').mockReturnValue(
      new Promise((resolve) => {
        settle = resolve;
      }),
    );
    renderPage();

    fillValidForm();
    fireEvent.click(submitButton());
    await waitFor(() => expect(submitButton()).toBeDisabled());

    // A disabled button stops a click, not a form submit from the keyboard.
    fireEvent.submit(submitButton().closest('form'));
    expect(createOrder).toHaveBeenCalledTimes(1);

    settle({ orderNumber: 'VB-20260918-1000' });
    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(createOrder).toHaveBeenCalledTimes(1);
  });
});
