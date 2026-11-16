/**
 * Smoke tests for CustomerDetail.
 *
 * What they cover: a customer with orders and addresses, one with neither, and
 * the error states - a failed load with retry, and a customer that does not exist.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';

import CustomerDetail from './CustomerDetail.jsx';
import * as adminApi from '../adminApi.js';
import { t } from '../../i18n/index.js';
import { ApiError, NotFoundError } from '../../services/errors.js';

function makeCustomer(overrides = {}) {
  return {
    id: 'c-1',
    firstName: 'ნინო',
    lastName: 'გელაშვილი',
    email: 'nino@example.com',
    phone: '555123456',
    isActive: true,
    createdAt: '2026-09-01T10:00:00Z',
    ordersCount: 1,
    totalSpent: '120.50',
    orders: [
      {
        id: 'o-1',
        orderNumber: 'VB-1001',
        status: 'pending',
        createdAt: '2026-10-01T10:00:00Z',
        total: '120.50',
      },
    ],
    addresses: [
      { id: 'a-1', label: 'სახლი', city: 'თბილისი', addressLine: 'რუსთაველი 1', isDefault: true },
    ],
    ...overrides,
  };
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/admin/customers/c-1']}>
      <Routes>
        <Route path="/admin/customers/:id" element={<CustomerDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('CustomerDetail', () => {
  it('shows the profile, order history and addresses', async () => {
    const get = vi.spyOn(adminApi, 'getCustomer').mockResolvedValue(makeCustomer());
    renderDetail();

    expect(await screen.findByRole('heading', { name: 'ნინო გელაშვილი' })).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith('c-1');
    expect(screen.getByRole('link', { name: 'VB-1001' })).toHaveAttribute(
      'href',
      '/admin/orders/o-1',
    );
    expect(screen.getByText(/რუსთაველი 1/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'დაბლოკვა' })).toBeInTheDocument();
  });

  it('shows the empty messages for a customer without orders or addresses', async () => {
    vi.spyOn(adminApi, 'getCustomer').mockResolvedValue(
      makeCustomer({ orders: [], addresses: [], ordersCount: 0, totalSpent: '0.00', phone: null }),
    );
    renderDetail();

    expect(await screen.findByText('შეკვეთა ჯერ არ გაუფორმებია.')).toBeInTheDocument();
    expect(screen.getByText('შენახული მისამართი არ არის.')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /VB-/ })).not.toBeInTheDocument();
  });

  it('shows the error state and loads again on retry', async () => {
    const get = vi
      .spyOn(adminApi, 'getCustomer')
      .mockRejectedValueOnce(new ApiError('სერვერი მიუწვდომელია', 500))
      .mockResolvedValue(makeCustomer());
    renderDetail();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('მომხმარებელი ვერ ჩაიტვირთა');
    expect(alert).toHaveTextContent('სერვერი მიუწვდომელია');

    await userEvent.click(screen.getByRole('button', { name: t('common.retry') }));
    expect(await screen.findByRole('heading', { name: 'ნინო გელაშვილი' })).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it('shows the same error state, with the not-found message, for a missing customer', async () => {
    vi.spyOn(adminApi, 'getCustomer').mockRejectedValue(new NotFoundError('მომხმარებელი ვერ მოიძებნა'));
    renderDetail();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('მომხმარებელი ვერ ჩაიტვირთა');
    expect(alert).toHaveTextContent('მომხმარებელი ვერ მოიძებნა');
    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument();
  });
});
