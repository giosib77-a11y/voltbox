/**
 * Smoke tests for InventoryList.
 *
 * What they cover: the table with stock rows, the empty result, and the error
 * state when the API fails.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import InventoryList from './InventoryList.jsx';
import * as adminApi from '../adminApi.js';
import { ApiError } from '../../services/errors.js';

function page(items) {
  return { items, page: 1, limit: 20, total: items.length, totalPages: 1 };
}

const ROW = {
  productId: 'p-1',
  name: 'USB კაბელი',
  sku: 'USB-001',
  stock: 7,
  stockStatus: 'in_stock',
  lowStockThreshold: 3,
};

function renderList() {
  return render(
    <MemoryRouter initialEntries={['/admin/inventory']}>
      <InventoryList />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('InventoryList', () => {
  it('lists products with their SKU and an adjust action', async () => {
    vi.spyOn(adminApi, 'listInventory').mockResolvedValue(page([ROW]));
    renderList();

    expect(await screen.findByText('USB კაბელი')).toBeInTheDocument();
    expect(screen.getByText('USB-001')).toBeInTheDocument();
    expect(screen.getByText('1 პროდუქტი')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /კორექტირება/ })).toBeInTheDocument();
  });

  it('shows the empty state when nothing matches', async () => {
    vi.spyOn(adminApi, 'listInventory').mockResolvedValue(page([]));
    renderList();

    expect(await screen.findByText('პროდუქტი ვერ მოიძებნა')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('shows the error state when the request fails', async () => {
    vi.spyOn(adminApi, 'listInventory').mockRejectedValue(new ApiError('სერვერი მიუწვდომელია', 500));
    renderList();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('მარაგი ვერ ჩაიტვირთა');
    expect(alert).toHaveTextContent('სერვერი მიუწვდომელია');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
