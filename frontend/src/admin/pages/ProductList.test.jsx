/**
 * Tests for ProductList's delete action.
 *
 * What they cover: deleting is permanent, so the confirmation has to say so;
 * and a product that has already been sold cannot be deleted at all. The API
 * answers 409 PRODUCT_IN_USE there, and the dialog has to turn that refusal
 * into the thing the admin can actually do - archive it - rather than showing
 * a dead end.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import ProductList from './ProductList.jsx';
import * as adminApi from '../adminApi.js';
import { ConflictError } from '../../services/errors.js';

const PRODUCT = {
  id: 'p-1',
  name: 'iPhone 15 Pro',
  slug: 'iphone-15-pro',
  sku: 'IP15P',
  categoryName: 'ტელეფონები',
  brandName: 'Apple',
  price: '3499.00',
  oldPrice: null,
  stock: 4,
  stockStatus: 'in_stock',
  isActive: true,
  archivedAt: null,
  createdAt: '2026-01-05T10:00:00Z',
  primaryImage: null,
};

const PAGE = { items: [PRODUCT], total: 1, page: 1, limit: 20, totalPages: 1 };

function renderList() {
  return render(
    <MemoryRouter initialEntries={['/admin/products']}>
      <ProductList />
    </MemoryRouter>,
  );
}

async function openDeleteDialog() {
  renderList();
  await userEvent.click(await screen.findByRole('button', { name: /iPhone 15 Pro — წაშლა/ }));
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(adminApi, 'listProducts').mockResolvedValue(PAGE);
  vi.spyOn(adminApi, 'listCategories').mockResolvedValue([]);
  vi.spyOn(adminApi, 'listBrands').mockResolvedValue([]);
});

describe('ProductList delete', () => {
  it('asks before deleting and names what will be lost', async () => {
    const remove = vi.spyOn(adminApi, 'deleteProduct').mockResolvedValue(null);
    await openDeleteDialog();

    // The dialog is open and nothing has been sent yet.
    expect(screen.getByText(/სამუდამოდ წაიშლება/)).toBeInTheDocument();
    expect(remove).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'სამუდამოდ წაშლა' }));

    expect(remove).toHaveBeenCalledWith('p-1');
  });

  it('offers archiving when the product has already been ordered', async () => {
    vi.spyOn(adminApi, 'deleteProduct').mockRejectedValue(
      new ConflictError('This product appears in orders', {
        code: 'PRODUCT_IN_USE',
        details: { ordersCount: 3 },
      }),
    );
    const archive = vi.spyOn(adminApi, 'archiveProduct').mockResolvedValue(PRODUCT);
    await openDeleteDialog();

    await userEvent.click(screen.getByRole('button', { name: 'სამუდამოდ წაშლა' }));

    // The refusal explains itself with the real number, not a generic message.
    expect(await screen.findByText(/3 შეკვეთა/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'არქივში გადატანა' }));

    expect(archive).toHaveBeenCalledWith('p-1');
  });

  it('keeps the dialog open and shows why when the server refuses for another reason', async () => {
    vi.spyOn(adminApi, 'deleteProduct').mockRejectedValue(
      new ConflictError('სერვერმა უარი თქვა', { code: 'SOMETHING_ELSE', details: null }),
    );
    await openDeleteDialog();

    await userEvent.click(screen.getByRole('button', { name: 'სამუდამოდ წაშლა' }));

    expect(await screen.findByText('სერვერმა უარი თქვა')).toBeInTheDocument();
    // Still a delete button - this was not the "archive instead" case.
    expect(screen.getByRole('button', { name: 'სამუდამოდ წაშლა' })).toBeInTheDocument();
  });
});
