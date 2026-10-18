/**
 * Tests for OrderDetail's trash actions.
 *
 * What they cover: moving an order to the trash (with the stock warning where the
 * units are still reserved), the trashed view (purge date, no status buttons,
 * one-click restore), permanent delete behind a dialog, and the failure paths -
 * a server refusal and a dead network leave the buttons usable.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';

import OrderDetail from './OrderDetail.jsx';
import * as adminApi from '../adminApi.js';
import { ApiError, ConflictError } from '../../services/errors.js';

const toast = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
}));
vi.mock('../../hooks/useToast.js', () => ({ useToast: () => toast }));

function makeOrder(overrides = {}) {
  return {
    id: 'o-1',
    orderNumber: 'VB-1001',
    status: 'pending',
    createdAt: '2026-10-01T10:00:00Z',
    deletedAt: null,
    purgeAt: null,
    allowedTransitions: ['confirmed', 'cancelled'],
    customerName: 'ნინო',
    phone: '555',
    email: null,
    city: 'თბილისი',
    customer: { address: 'რუსთაველი 1' },
    notes: null,
    paymentMethod: 'cash',
    subtotal: '10.00',
    shipping: '0.00',
    total: '10.00',
    items: [],
    history: [],
    ...overrides,
  };
}

const TRASHED = makeOrder({
  deletedAt: '2026-10-10T10:00:00Z',
  purgeAt: '2026-11-09T10:00:00Z',
  allowedTransitions: [],
});

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/admin/orders/o-1']}>
      <Routes>
        <Route path="/admin/orders/:id" element={<OrderDetail />} />
        <Route path="/admin/orders" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  toast.success.mockClear();
});

describe('OrderDetail move to trash', () => {
  it('warns that the units stay reserved for a pending order', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(makeOrder());
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'წაშლა' }));

    expect(screen.getByText(/ერთეულები დარჩება დაკავებული/)).toBeInTheDocument();
  });

  it('does not show the stock warning for a delivered order', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(
      makeOrder({ status: 'delivered', allowedTransitions: [] }),
    );
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'წაშლა' }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.queryByText(/ერთეულები დარჩება დაკავებული/)).not.toBeInTheDocument();
  });

  it('trashes once on confirm and lands on the list with a toast', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(makeOrder());
    const trash = vi.spyOn(adminApi, 'trashOrder').mockResolvedValue(TRASHED);
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'წაშლა' }));
    expect(trash).not.toHaveBeenCalled();
    await userEvent.click(screen.getAllByRole('button', { name: 'წაშლა' }).at(-1));

    expect(await screen.findByTestId('where')).toHaveTextContent('/admin/orders');
    expect(trash).toHaveBeenCalledTimes(1);
    expect(trash).toHaveBeenCalledWith('o-1');
    expect(toast.success).toHaveBeenCalledTimes(1);
  });

  it('shows the server message and keeps the page usable when trashing fails', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(makeOrder());
    vi.spyOn(adminApi, 'trashOrder').mockRejectedValue(new ApiError('ქსელის შეცდომა', 0));
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'წაშლა' }));
    await userEvent.click(screen.getAllByRole('button', { name: 'წაშლა' }).at(-1));

    expect(await screen.findByRole('alert')).toHaveTextContent('ქსელის შეცდომა');
    expect(screen.getByRole('button', { name: 'წაშლა' })).toBeEnabled();
    expect(screen.queryByTestId('where')).not.toBeInTheDocument();
  });
});

describe('OrderDetail trashed order', () => {
  it('shows the purge date and no status buttons', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(TRASHED);
    renderDetail();

    expect(await screen.findByText(/სამუდამოდ წაიშლება/)).toHaveTextContent('2026');
    expect(screen.getByRole('button', { name: 'აღდგენა' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'დადასტურებული' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'წაშლა' })).not.toBeInTheDocument();
  });

  it('restores in one click, without a dialog, and shows the live order', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(TRASHED);
    const restore = vi.spyOn(adminApi, 'restoreOrder').mockResolvedValue(makeOrder());
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'აღდგენა' }));

    expect(restore).toHaveBeenCalledWith('o-1');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'წაშლა' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'აღდგენა' })).not.toBeInTheDocument();
  });

  it('needs the dialog to delete forever, then lands on the trash list', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(TRASHED);
    const remove = vi.spyOn(adminApi, 'deleteOrderForever').mockResolvedValue(null);
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'სამუდამოდ წაშლა' }));
    expect(remove).not.toHaveBeenCalled();
    expect(screen.getByText(/აღდგენა შეუძლებელი იქნება/)).toBeInTheDocument();

    await userEvent.click(screen.getAllByRole('button', { name: 'სამუდამოდ წაშლა' }).at(-1));

    expect(await screen.findByTestId('where')).toHaveTextContent('/admin/orders?trash=true');
    expect(remove).toHaveBeenCalledWith('o-1');
  });

  it('shows ORDER_NOT_IN_TRASH when the order was restored elsewhere', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(TRASHED);
    vi.spyOn(adminApi, 'deleteOrderForever').mockRejectedValue(
      new ConflictError('შეკვეთა სანაგვეში არ არის', {
        code: 'ORDER_NOT_IN_TRASH',
      }),
    );
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'სამუდამოდ წაშლა' }));
    await userEvent.click(screen.getAllByRole('button', { name: 'სამუდამოდ წაშლა' }).at(-1));

    expect(await screen.findByRole('alert')).toHaveTextContent('შეკვეთა სანაგვეში არ არის');
    expect(screen.getByRole('button', { name: 'აღდგენა' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'სამუდამოდ წაშლა' })).toBeEnabled();
  });

  it('shows the message and re-enables restore when restoring fails', async () => {
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(TRASHED);
    vi.spyOn(adminApi, 'restoreOrder').mockRejectedValue(new ApiError('ქსელის შეცდომა', 0));
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'აღდგენა' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('ქსელის შეცდომა');
    expect(screen.getByRole('button', { name: 'აღდგენა' })).toBeEnabled();
  });
});

describe('OrderDetail status change on a trashed order', () => {
  it('shows ORDER_IN_TRASH and keeps the buttons enabled', async () => {
    // The page was loaded live, then the order was trashed in another tab.
    vi.spyOn(adminApi, 'getOrder').mockResolvedValue(makeOrder());
    vi.spyOn(adminApi, 'changeOrderStatus').mockRejectedValue(
      new ConflictError('შეკვეთა სანაგვეშია', { code: 'ORDER_IN_TRASH' }),
    );
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'დადასტურებული' }));
    await userEvent.click(screen.getByRole('button', { name: 'დადასტურება' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('შეკვეთა სანაგვეშია');
    expect(screen.getByRole('button', { name: 'დადასტურებული' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'წაშლა' })).toBeEnabled();
  });
});
