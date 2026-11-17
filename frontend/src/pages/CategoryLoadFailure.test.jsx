/**
 * A categories load that fails once does not turn the category page into
 * "not found" for the rest of the page's life (A-110).
 *
 * useCategories used to keep even a rejected promise, so every later mount got
 * the same rejection and only a full reload helped. A failed answer is now
 * dropped from the cache; the next mount asks again.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';

vi.mock('../hooks/useCart.js', () => ({ useCart: () => ({ addItem: () => {}, quantities: {} }) }));
vi.mock('../hooks/useToast.js', () => ({ useToast: () => ({ success: () => {} }) }));

import * as api from '../services/api.js';
import Category from './Category.jsx';
import { forgetCategories } from '../hooks/useProducts.js';
import { t } from '../i18n/index.js';

const CABLES = {
  id: 'c-cables',
  slug: 'cables',
  name: 'კაბელები',
  icon: 'Cable',
  parentId: null,
  position: 1,
  productsCount: 0,
  filters: [],
};

beforeEach(() => {
  forgetCategories();
  vi.spyOn(api, 'getProducts').mockResolvedValue({
    items: [],
    total: 0,
    facets: { values: {}, price: { min: 0, max: 0 } },
  });
});

afterEach(() => vi.restoreAllMocks());

function mountCategory() {
  const router = createMemoryRouter([{ path: '/category/:slug', element: <Category /> }], {
    initialEntries: ['/category/cables'],
  });
  return render(<RouterProvider router={router} />);
}

describe('Category page after a failed categories load', () => {
  it('asks for the categories again on the next mount and shows the category', async () => {
    const getCategories = vi
      .spyOn(api, 'getCategories')
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValue([CABLES]);

    const first = mountCategory();
    expect(await screen.findByText(t('catalog.categoryNotFound'))).toBeTruthy();
    first.unmount();

    mountCategory();
    expect(await screen.findByRole('heading', { name: CABLES.name })).toBeTruthy();
    expect(screen.queryByText(t('catalog.categoryNotFound'))).toBeNull();
    expect(getCategories).toHaveBeenCalledTimes(2);
  });

  it('keeps a successful answer for later mounts', async () => {
    const getCategories = vi.spyOn(api, 'getCategories').mockResolvedValue([CABLES]);

    const first = mountCategory();
    expect(await screen.findByRole('heading', { name: CABLES.name })).toBeTruthy();
    first.unmount();

    mountCategory();
    expect(await screen.findByRole('heading', { name: CABLES.name })).toBeTruthy();
    expect(getCategories).toHaveBeenCalledTimes(1);
  });
});
