/**
 * The hero's buttons lead to a category that exists, whichever the owner has
 * deleted.
 *
 * They used to be `/category/phones` and `/category/headphones`, written into
 * Home.jsx. The owner deleted Phones in the admin, and the home page's main
 * button opened "category not found". Each test follows the buttons through a
 * real router into the real category page, so a link to a category the API no
 * longer returns shows up as that page's not-found state.
 *
 * Notes: useCategories keeps its first answer for the whole module, so each
 * test loads the modules afresh to give it a different list.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';

// A product card has an add-to-cart button; the cart itself is not what these check
vi.mock('../hooks/useCart.js', () => ({ useCart: () => ({ addItem: () => {}, quantities: {} }) }));
vi.mock('../hooks/useToast.js', () => ({ useToast: () => ({ success: () => {} }) }));

const category = (slug, name, position, parentId = null) => ({
  id: `c-${slug}`,
  slug,
  name,
  icon: 'Cable',
  parentId,
  position,
  productsCount: 3,
  filters: [],
});

/** What GET /categories returns once the owner has deleted Phones. */
const AFTER_PHONES_DELETED = [
  category('headphones', 'ყურსასმენები', 1),
  category('earbuds', 'უსადენო', 2, 'c-headphones'),
  category('cables', 'კაბელები', 3),
  category('chargers', 'დამტენები', 4),
];

afterEach(() => vi.restoreAllMocks());

async function mountHome(categories) {
  vi.resetModules();
  const api = await import('../services/api.js');
  const { default: Home } = await import('./Home.jsx');
  const { default: Category } = await import('./Category.jsx');

  vi.spyOn(api, 'getCategories').mockResolvedValue(categories);
  vi.spyOn(api, 'getHomeSections').mockResolvedValue({
    newArrivals: [],
    discounted: [],
    featured: [],
    latest: [],
    popularCategories: categories,
  });
  vi.spyOn(api, 'getDeliveryRules').mockResolvedValue({ cities: [], freeFrom: 50, currency: 'GEL' });
  vi.spyOn(api, 'getProducts').mockResolvedValue({
    items: [],
    total: 0,
    facets: { values: {}, price: { min: 0, max: 0 } },
  });

  const router = createMemoryRouter(
    [
      { path: '/', element: <Home /> },
      { path: '/category/:slug', element: <Category /> },
    ],
    { initialEntries: ['/'] },
  );
  render(<RouterProvider router={router} />);
  return { router, api };
}

/** The links inside the hero - the section with the page's only h1. */
async function heroLinks() {
  const heading = await screen.findByRole('heading', { level: 1 });
  return within(heading.closest('section')).queryAllByRole('link');
}

describe('the home hero buttons', () => {
  it('each opens a category that exists after Phones is deleted', async () => {
    const user = userEvent.setup();
    const { router } = await mountHome(AFTER_PHONES_DELETED);

    // The owner's first two top-level categories, in the owner's order; the
    // subcategory between them is not one of them
    await screen.findAllByRole('link', { name: 'კაბელები', hidden: true });
    const links = await heroLinks();
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/category/headphones',
      '/category/cables',
    ]);

    for (const name of ['ყურსასმენები', 'კაბელები']) {
      await user.click((await heroLinks()).find((link) => link.textContent === name));
      expect(
        await screen.findByRole('heading', { level: 1, name }),
      ).toBeInTheDocument();
      expect(screen.queryByText('კატეგორია ვერ მოიძებნა')).toBeNull();
      await act(() => router.navigate('/'));
    }
  });

  it('shows no button, rather than a broken one, when no category is left', async () => {
    const { api } = await mountHome([]);

    await screen.findByRole('heading', { level: 1 });
    // Checked after the list has arrived, not while it is still loading
    await act(() => api.getCategories.mock.results[0].value);
    expect(await heroLinks()).toEqual([]);
  });
});
