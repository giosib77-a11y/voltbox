/**
 * Tests for the customer's order list.
 *
 * What they cover: that every status the server can send has words of its own.
 * The list used to know four of the six, and the two it did not know -
 * `confirmed` and `cancelled` - fell through to `pending`. A cancelled order
 * therefore told the person who placed it that it was being prepared, and they
 * waited for a delivery that was never coming.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import Orders from './Orders.jsx';
import * as api from '../../services/api.js';
import { ORDER_STATUS_LABELS } from '../../constants/index.js';

const order = (status) => ({
  orderNumber: `VB-20260912-${status.length}000`,
  createdAt: '2026-09-12T10:00:00Z',
  status,
  customer: { city: 'თბილისი', address: 'ჭავჭავაძის 42' },
  totals: { total: 80 },
  items: [
    {
      productId: 'p1',
      qty: 2,
      snapshot: { name: 'Cable', slug: 'cable', image: '/a.png', price: 40 },
    },
  ],
});

function renderOrders() {
  return render(
    <MemoryRouter>
      <Orders />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('the order list', () => {
  it.each(Object.keys(ORDER_STATUS_LABELS))('names the %s status in the customer\'s words', async (
    status,
  ) => {
    vi.spyOn(api, 'getOrders').mockResolvedValue([order(status)]);
    renderOrders();

    expect(await screen.findByText(ORDER_STATUS_LABELS[status].label)).toBeInTheDocument();
  });

  it('never tells a cancelled order it is being prepared', async () => {
    vi.spyOn(api, 'getOrders').mockResolvedValue([order('cancelled')]);
    renderOrders();

    expect(await screen.findByText('გაუქმებულია')).toBeInTheDocument();
    expect(screen.queryByText('მზადდება')).not.toBeInTheDocument();
    expect(screen.queryByText('მიღებულია')).not.toBeInTheDocument();
  });

  it('says nothing rather than guessing at a status it does not know', async () => {
    // Guessing is what produced the bug above: an unrecognised status used to
    // borrow `pending`'s words.
    vi.spyOn(api, 'getOrders').mockResolvedValue([order('refunded')]);
    renderOrders();

    expect(await screen.findByText('—')).toBeInTheDocument();
    expect(screen.queryByText('მიღებულია')).not.toBeInTheDocument();
  });
});
