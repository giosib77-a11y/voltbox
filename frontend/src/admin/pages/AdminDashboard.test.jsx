/**
 * Smoke tests for AdminDashboard.
 *
 * What they cover: the KPIs and panels filled from one response, the all-zero
 * response with every panel's empty message, and the error state with retry.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';

import AdminDashboard from './AdminDashboard.jsx';
import * as adminApi from '../adminApi.js';
import { t } from '../../i18n/index.js';
import { ApiError } from '../../services/errors.js';

const FULL = {
  salesToday: '250.00',
  ordersToday: 3,
  salesTotal: '9000.00',
  activeProducts: 42,
  lowStockCount: 2,
  ordersByStatus: { pending: 5, confirmed: 1 },
  latestOrders: [{ id: 'o-1', orderNumber: 'VB-1001', status: 'pending', total: '10.00' }],
  lowStock: [{ id: 'p-1', name: 'სწრაფი დამტენი', stock: 1, threshold: 5 }],
  topProducts: [{ productId: 'p-2', name: 'USB კაბელი', quantity: 9, revenue: '90.00' }],
  latestProducts: [{ id: 'p-3', name: 'ყურსასმენი', price: '35.00' }],
};

const EMPTY = {
  salesToday: '0.00',
  ordersToday: 0,
  salesTotal: '0.00',
  activeProducts: 0,
  lowStockCount: 0,
  ordersByStatus: {},
  latestOrders: [],
  lowStock: [],
  topProducts: [],
  latestProducts: [],
};

function renderDashboard() {
  return render(
    <MemoryRouter>
      <AdminDashboard />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('AdminDashboard', () => {
  it('shows the figures and the lists from the response', async () => {
    vi.spyOn(adminApi, 'getDashboard').mockResolvedValue(FULL);
    renderDashboard();

    expect(await screen.findByRole('heading', { name: 'მიმოხილვა' })).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('2 იწურება')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'VB-1001' })).toHaveAttribute('href', '/admin/orders/o-1');
    expect(screen.getByText('სწრაფი დამტენი')).toBeInTheDocument();
    expect(screen.getByText('USB კაბელი')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'ყურსასმენი' })).toHaveAttribute(
      'href',
      '/admin/products/p-3',
    );
    expect(screen.queryByText('შეკვეთა ჯერ არ არის.')).not.toBeInTheDocument();
  });

  it('shows every empty message when the shop has no data', async () => {
    vi.spyOn(adminApi, 'getDashboard').mockResolvedValue(EMPTY);
    renderDashboard();

    expect(await screen.findByText('შეკვეთა ჯერ არ არის.')).toBeInTheDocument();
    expect(screen.getByText('ყველა პროდუქტს საკმარისი მარაგი აქვს.')).toBeInTheDocument();
    expect(screen.getByText('ბოლო 30 დღეში გაყიდვა არ ყოფილა.')).toBeInTheDocument();
    expect(screen.getByText('პროდუქტი ჯერ არ არის.')).toBeInTheDocument();
    expect(screen.getByText('მარაგი წესრიგშია')).toBeInTheDocument();
  });

  it('shows the error state and loads again on retry', async () => {
    const get = vi
      .spyOn(adminApi, 'getDashboard')
      .mockRejectedValueOnce(new ApiError('სერვერი მიუწვდომელია', 500))
      .mockResolvedValue(EMPTY);
    renderDashboard();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('მაჩვენებლები ვერ ჩაიტვირთა');
    expect(alert).toHaveTextContent('სერვერი მიუწვდომელია');

    await userEvent.click(screen.getByRole('button', { name: t('common.retry') }));
    expect(await screen.findByRole('heading', { name: 'მიმოხილვა' })).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(2);
  });
});
