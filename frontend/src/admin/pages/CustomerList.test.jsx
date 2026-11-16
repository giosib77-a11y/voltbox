/**
 * Smoke tests for CustomerList.
 *
 * What they cover: the table with customers (name, status, link to detail), the
 * empty result, and the error state when the API fails.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import CustomerList from './CustomerList.jsx';
import * as adminApi from '../adminApi.js';
import { ApiError } from '../../services/errors.js';

function page(items) {
  return { items, page: 1, limit: 20, total: items.length, totalPages: 1 };
}

const CUSTOMER = {
  id: 'c-1',
  firstName: 'ნინო',
  lastName: 'გელაშვილი',
  email: 'nino@example.com',
  phone: null,
  ordersCount: 2,
  totalSpent: '120.50',
  isActive: false,
  createdAt: '2026-09-01T10:00:00Z',
};

function renderList() {
  return render(
    <MemoryRouter initialEntries={['/admin/customers']}>
      <CustomerList />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('CustomerList', () => {
  it('lists customers with a link to each and their blocked status', async () => {
    vi.spyOn(adminApi, 'listCustomers').mockResolvedValue(page([CUSTOMER]));
    renderList();

    const link = await screen.findByRole('link', { name: /ნინო გელაშვილი/ });
    expect(link).toHaveAttribute('href', '/admin/customers/c-1');
    expect(screen.getByText('nino@example.com')).toBeInTheDocument();
    expect(screen.getByText('დაბლოკილი', { selector: 'span.inline-flex' })).toBeInTheDocument();
    expect(screen.getByText('1 ჩანაწერი')).toBeInTheDocument();
  });

  it('shows the empty state when no customer matches', async () => {
    vi.spyOn(adminApi, 'listCustomers').mockResolvedValue(page([]));
    renderList();

    expect(await screen.findByText('მომხმარებელი ვერ მოიძებნა')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('shows the error state when the request fails', async () => {
    vi.spyOn(adminApi, 'listCustomers').mockRejectedValue(new ApiError('სერვერი მიუწვდომელია', 500));
    renderList();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('მომხმარებლები ვერ ჩაიტვირთა');
    expect(alert).toHaveTextContent('სერვერი მიუწვდომელია');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
