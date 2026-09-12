/**
 * Tests for the order page a customer sees.
 *
 * This one screen is two things: the thank-you straight after checkout, and the
 * order's detail view, reached from "დეტალების ნახვა" in the account weeks
 * later. It used to render the first of those unconditionally - a green tick,
 * "შეკვეთა მიღებულია!", a promise that an operator would call and an estimated
 * delivery date - on an order the shop had already cancelled.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import CheckoutSuccess from './CheckoutSuccess.jsx';
import * as api from '../services/api.js';
import { ToastProvider } from '../context/ToastContext.jsx';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: () => ({ id: 'VB-20260912-1000' }) };
});

const order = (status) => ({
  orderNumber: 'VB-20260912-1000',
  createdAt: '2026-09-12T10:00:00Z',
  status,
  paymentMethod: 'cash',
  currency: 'GEL',
  customer: {
    firstName: 'გიორგი',
    lastName: 'ბერიძე',
    phone: '555123456',
    city: 'თბილისი',
    address: 'ჭავჭავაძის 42',
  },
  totals: { subtotal: 80, shipping: 0, total: 80 },
  items: [
    {
      productId: 'p1',
      qty: 2,
      snapshot: { name: 'Cable', slug: 'cable', image: '/a.png', price: 40 },
    },
  ],
});

const renderPage = () =>
  render(
    <ToastProvider>
      <MemoryRouter>
        <CheckoutSuccess />
      </MemoryRouter>
    </ToastProvider>,
  );

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('the order page', () => {
  it('thanks the customer for an order that was just placed', async () => {
    vi.spyOn(api, 'getOrderByNumber').mockResolvedValue(order('pending'));
    renderPage();

    expect(await screen.findByText('შეკვეთა მიღებულია!')).toBeInTheDocument();
    expect(screen.getByText(/ოპერატორი დაგიკავშირდებათ/)).toBeInTheDocument();
    expect(screen.getByText(/სავარაუდო მიწოდება/)).toBeInTheDocument();
  });

  it('does not congratulate somebody on an order that was cancelled', async () => {
    vi.spyOn(api, 'getOrderByNumber').mockResolvedValue(order('cancelled'));
    renderPage();

    expect(await screen.findByText('შეკვეთა გაუქმებულია')).toBeInTheDocument();
    expect(screen.queryByText('შეკვეთა მიღებულია!')).not.toBeInTheDocument();
    // Neither of these can be true of a cancelled order.
    expect(screen.queryByText(/ოპერატორი დაგიკავშირდებათ/)).not.toBeInTheDocument();
    expect(screen.queryByText(/სავარაუდო მიწოდება/)).not.toBeInTheDocument();
  });

  it('shows the status wherever the order has got to', async () => {
    vi.spyOn(api, 'getOrderByNumber').mockResolvedValue(order('shipped'));
    renderPage();

    expect(await screen.findByText('გზაშია')).toBeInTheDocument();
  });

  it('does not promise a delivery that has already happened', async () => {
    vi.spyOn(api, 'getOrderByNumber').mockResolvedValue(order('delivered'));
    renderPage();

    expect(await screen.findByText('შეკვეთა ჩაბარებულია')).toBeInTheDocument();
    expect(screen.queryByText(/სავარაუდო მიწოდება/)).not.toBeInTheDocument();
  });
});
