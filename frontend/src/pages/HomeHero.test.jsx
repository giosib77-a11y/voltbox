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
 * test clears that cache (and the delivery rules') to give it a different list.
 * The modules are imported once, at the top: re-importing the whole page graph
 * inside the test (`vi.resetModules()`) took about half of its time - 0.7 s of
 * 1.3 s measured on a quiet machine - and under CPU load that pushed it over
 * the 5 s timeout.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';

// A product card has an add-to-cart button; the cart itself is not what these check
vi.mock('../hooks/useCart.js', () => ({ useCart: () => ({ addItem: () => {}, quantities: {} }) }));
vi.mock('../hooks/useToast.js', () => ({ useToast: () => ({ success: () => {} }) }));

import * as api from '../services/api.js';
import Home from './Home.jsx';
import Category from './Category.jsx';
import { forgetCategories } from '../hooks/useProducts.js';
import { forgetDeliveryRules } from '../hooks/useDeliveryRules.js';

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

beforeEach(() => {
  forgetCategories();
  forgetDeliveryRules();
});

afterEach(() => vi.restoreAllMocks());

async function mountHome(categories) {
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
  // The mocked answers are already resolved, so they land in the microtasks
  // right after render, before the caller's first findBy has switched act off.
  await pageSettled(api);
  return { router, api };
}

/**
 * Until every request the page has made so far has been answered and drawn.
 *
 * The hero is on screen before the sections below it have their data; a test
 * that ends in between sees those answers land outside act(). The answers are
 * the mocked promises themselves, so this waits for exactly them, inside act.
 * The extra macrotask lets the `.then().catch().finally()` chains behind them
 * (useAsync) run to their last state update before act closes.
 */
async function pageSettled(api) {
  await act(async () => {
    const spies = [api.getCategories, api.getHomeSections, api.getDeliveryRules, api.getProducts];
    await Promise.all(spies.flatMap((spy) => spy.mock.results.map((result) => result.value)));
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

/** The links inside the hero - the section with the page's only h1. */
async function heroLinks() {
  const heading = await screen.findByRole('heading', { level: 1 });
  return within(heading.closest('section')).queryAllByRole('link');
}

describe('the home hero buttons', () => {
  it('each opens a category that exists after Phones is deleted', async () => {
    const user = userEvent.setup();
    const { router, api } = await mountHome(AFTER_PHONES_DELETED);

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
      await pageSettled(api);
    }
  });

  it('shows no button, rather than a broken one, when no category is left', async () => {
    const { api } = await mountHome([]);

    await screen.findByRole('heading', { level: 1 });
    // Checked after the list has arrived, not while it is still loading
    await pageSettled(api);
    expect(await heroLinks()).toEqual([]);
  });
});
