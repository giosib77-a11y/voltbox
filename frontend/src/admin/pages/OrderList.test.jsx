/**
 * Tests for OrderList's trash mode.
 *
 * What they cover: the "სანაგვე" toggle (API parameter and URL), the days left
 * before the purge, per-row restore and permanent delete (the latter behind a
 * dialog), the list reloading after each, and the failure paths.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router';

import OrderList from './OrderList.jsx';
import * as adminApi from '../adminApi.js';
import { ApiError, ConflictError, NotFoundError } from '../../services/errors.js';

const DAY = 86_400_000;

function makeOrder(overrides = {}) {
  return {
    id: 'o-1',
    orderNumber: 'VB-1001',
    status: 'pending',
    customerName: 'ნინო',
    phone: '555',
    email: null,
    city: 'თბილისი',
    itemCount: 2,
    total: '10.00',
    createdAt: '2026-10-01T10:00:00Z',
    deletedAt: null,
    purgeAt: null,
    ...overrides,
  };
}

function pageOf(items) {
  return { items, total: items.length, page: 1, limit: 20, totalPages: 1 };
}

function trashed(overrides = {}) {
  return makeOrder({
    deletedAt: '2026-10-10T10:00:00Z',
    purgeAt: new Date(Date.now() + 12 * DAY - 60_000).toISOString(),
    ...overrides,
  });
}

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.search}</p>;
}

function renderList(url = '/admin/orders') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <OrderList />
      <Where />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('OrderList trash toggle', () => {
  it('lists live orders by default and the trash after the toggle', async () => {
    const list = vi
      .spyOn(adminApi, 'listOrders')
      .mockImplementation(async (params) =>
        params.trash ? pageOf([trashed()]) : pageOf([makeOrder()]),
      );
    renderList('/admin/orders?page=2');

    await screen.findByText('VB-1001');
    expect(list.mock.calls[0][0].trash).toBeUndefined();

    await userEvent.click(screen.getByRole('checkbox', { name: 'სანაგვე' }));

    expect(await screen.findByRole('button', { name: /აღდგენა/ })).toBeInTheDocument();
    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ trash: true, page: 1 }));
    expect(screen.getByTestId('where')).toHaveTextContent('trash=true');
    expect(screen.getByTestId('where')).not.toHaveTextContent('page=2');
    // Rows still link to the detail page.
    expect(screen.getByRole('link', { name: 'VB-1001' })).toHaveAttribute(
      'href',
      '/admin/orders/o-1',
    );
  });

  it('shows days left from purgeAt, never below zero', async () => {
    vi.spyOn(adminApi, 'listOrders').mockResolvedValue(
      pageOf([
        trashed({ id: 'a', orderNumber: 'VB-1' }),
        trashed({
          id: 'b',
          orderNumber: 'VB-2',
          purgeAt: new Date(Date.now() - 3 * DAY).toISOString(),
        }),
      ]),
    );
    renderList('/admin/orders?trash=true');

    const first = (await screen.findByText('VB-1')).closest('tr');
    const second = screen.getByText('VB-2').closest('tr');
    expect(within(first).getByText('12 დღე')).toBeInTheDocument();
    expect(within(second).getByText('0 დღე')).toBeInTheDocument();
  });

  it('says so when the trash is empty', async () => {
    vi.spyOn(adminApi, 'listOrders').mockResolvedValue(pageOf([]));
    renderList('/admin/orders?trash=true');

    expect(await screen.findByText('სანაგვე ცარიელია')).toBeInTheDocument();
  });
});

describe('OrderList row actions in the trash', () => {
  it('restores a row and reloads the list', async () => {
    const list = vi
      .spyOn(adminApi, 'listOrders')
      .mockResolvedValueOnce(pageOf([trashed()]))
      .mockResolvedValue(pageOf([]));
    const restore = vi.spyOn(adminApi, 'restoreOrder').mockResolvedValue(makeOrder());
    renderList('/admin/orders?trash=true');

    await userEvent.click(await screen.findByRole('button', { name: 'VB-1001 — აღდგენა' }));

    expect(restore).toHaveBeenCalledWith('o-1');
    expect(await screen.findByText('სანაგვე ცარიელია')).toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(2);
  });

  it('deletes a row for good only after the dialog, then reloads', async () => {
    const list = vi
      .spyOn(adminApi, 'listOrders')
      .mockResolvedValueOnce(pageOf([trashed()]))
      .mockResolvedValue(pageOf([]));
    const remove = vi.spyOn(adminApi, 'deleteOrderForever').mockResolvedValue(null);
    renderList('/admin/orders?trash=true');

    await userEvent.click(await screen.findByRole('button', { name: 'VB-1001 — სამუდამოდ წაშლა' }));
    expect(remove).not.toHaveBeenCalled();
    expect(screen.getByText(/აღდგენა შეუძლებელი იქნება/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'სამუდამოდ წაშლა' }));

    expect(remove).toHaveBeenCalledWith('o-1');
    expect(await screen.findByText('სანაგვე ცარიელია')).toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(2);
  });

  it.each([
    [
      'ORDER_NOT_IN_TRASH',
      new ConflictError('შეკვეთა სანაგვეში არ არის', { code: 'ORDER_NOT_IN_TRASH' }),
    ],
    ['ORDER_NOT_FOUND', new NotFoundError('შეკვეთა ვერ მოიძებნა')],
  ])('closes the dialog and reloads the list on %s', async (_code, failure) => {
    const list = vi
      .spyOn(adminApi, 'listOrders')
      .mockResolvedValueOnce(pageOf([trashed()]))
      .mockResolvedValue(pageOf([]));
    vi.spyOn(adminApi, 'deleteOrderForever').mockRejectedValue(failure);
    renderList('/admin/orders?trash=true');

    await userEvent.click(await screen.findByRole('button', { name: 'VB-1001 — სამუდამოდ წაშლა' }));
    await userEvent.click(screen.getByRole('button', { name: 'სამუდამოდ წაშლა' }));

    expect(await screen.findByText('სანაგვე ცარიელია')).toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows the message and keeps row buttons enabled when restore hits the network error', async () => {
    vi.spyOn(adminApi, 'listOrders').mockResolvedValue(pageOf([trashed()]));
    vi.spyOn(adminApi, 'restoreOrder').mockRejectedValue(new ApiError('ქსელის შეცდომა', 0));
    renderList('/admin/orders?trash=true');

    await userEvent.click(await screen.findByRole('button', { name: 'VB-1001 — აღდგენა' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('ქსელის შეცდომა');
    expect(screen.getByRole('button', { name: 'VB-1001 — აღდგენა' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'VB-1001 — სამუდამოდ წაშლა' })).toBeEnabled();
  });

  it('keeps the dialog open with an alert under the description on a network error', async () => {
    const list = vi.spyOn(adminApi, 'listOrders').mockResolvedValue(pageOf([trashed()]));
    vi.spyOn(adminApi, 'deleteOrderForever').mockRejectedValue(new ApiError('ქსელის შეცდომა', 0));
    renderList('/admin/orders?trash=true');

    await userEvent.click(await screen.findByRole('button', { name: 'VB-1001 — სამუდამოდ წაშლა' }));
    await userEvent.click(screen.getByRole('button', { name: 'სამუდამოდ წაშლა' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('ქსელის შეცდომა');
    expect(screen.getByText(/ქმედება შეუქცევადია/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'სამუდამოდ წაშლა' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'გაუქმება' })).toBeEnabled();
    expect(list).toHaveBeenCalledTimes(1);
  });
});

describe('OrderList columns', () => {
  const headers = () => screen.getAllByRole('columnheader').map((cell) => cell.textContent);

  it('keeps the live view headers', async () => {
    vi.spyOn(adminApi, 'listOrders').mockResolvedValue(pageOf([makeOrder()]));
    renderList();
    await screen.findByText('VB-1001');

    expect(headers()).toEqual([
      'შეკვეთა',
      'მყიდველი',
      'ქალაქი',
      'პოზიცია',
      'ჯამი',
      'სტატუსი',
      'თარიღი',
    ]);
  });

  it('drops city, item count and order date in the trash and merges the two trash dates', async () => {
    vi.spyOn(adminApi, 'listOrders').mockResolvedValue(pageOf([trashed()]));
    renderList('/admin/orders?trash=true');
    await screen.findByText('VB-1001');

    const shown = headers().filter(Boolean);
    expect(shown).toEqual(['შეკვეთა', 'მყიდველი', 'ჯამი', 'სტატუსი', 'წაშლილია']);
    expect(screen.queryByRole('columnheader', { name: 'დარჩა' })).not.toBeInTheDocument();
    expect(screen.getByText('12 დღე')).toBeInTheDocument();
  });
});
