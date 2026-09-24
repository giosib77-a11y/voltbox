/**
 * The home page's category grid shows top-level categories only. A
 * subcategory's products are already counted in its parent's card, so a card
 * of its own beside the parent would be both misplaced and counted twice.
 *
 * Beside the hero, the vertical category menu lists the same roots, with the
 * subcategories in their flyouts.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { HOME_SECTION_TITLES } from '../constants/index.js';

import Home from './Home.jsx';
import * as api from '../services/api.js';

// A product card has an add-to-cart button; the cart itself is not what these check
vi.mock('../hooks/useCart.js', () => ({ useCart: () => ({ addItem: () => {}, quantities: {} }) }));
vi.mock('../hooks/useToast.js', () => ({ useToast: () => ({ success: () => {} }) }));

const POPULAR = [
  { id: 'c-phones', slug: 'phones', name: 'ტელეფონები', icon: 'Smartphone', parentId: null, productsCount: 4 },
  { id: 'c-samsung', slug: 'samsung', name: 'Samsung', icon: 'Smartphone', parentId: 'c-phones', productsCount: 1 },
  { id: 'c-cables', slug: 'cables', name: 'კაბელები', icon: 'Cable', parentId: null, productsCount: 2 },
];

// useCategories keeps the first answer for the whole module, so every test
// gets the same one
beforeEach(() => {
  vi.spyOn(api, 'getHomeSections').mockResolvedValue({
    newArrivals: [],
    discounted: [],
    featured: [],
    popularCategories: POPULAR,
  });
  vi.spyOn(api, 'getCategories').mockResolvedValue(POPULAR);
});

afterEach(() => vi.restoreAllMocks());

const PRODUCT = (slug, name) => ({
  id: `p-${slug}`,
  slug,
  name,
  brand: 'Anker',
  price: 45.5,
  oldPrice: null,
  hasDiscount: false,
  discountPercent: 0,
  images: [],
  rating: 0,
  reviewsCount: 0,
  inStock: true,
  stock: 5,
  isNew: false,
  isFeatured: false,
});

function mount() {
  render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>
  );
}

describe('Home', () => {
  it('shows root categories in the grid and no subcategory', async () => {
    mount();

    const heading = await screen.findByRole('heading', { name: HOME_SECTION_TITLES.popularCategories });
    const grid = within(heading.closest('section'));
    expect(await grid.findByRole('link', { name: /ტელეფონები/ })).toHaveAttribute(
      'href',
      '/category/phones'
    );
    expect(grid.getByRole('link', { name: /კაბელები/ })).toBeInTheDocument();
    expect(grid.queryByRole('link', { name: /Samsung/ })).toBeNull();
  });

  it('lists the root categories in the menu beside the hero', async () => {
    mount();

    const nav = await screen.findByRole('navigation', { name: 'კატეგორიები' });
    const menu = within(nav);
    expect(await menu.findByRole('link', { name: 'ტელეფონები' })).toHaveAttribute('href', '/category/phones');
    expect(menu.getByRole('link', { name: 'კაბელები' })).toBeInTheDocument();
    // Samsung is in the Phones flyout, closed until Phones is hovered or focused
    expect(menu.queryByRole('link', { name: 'Samsung' })).toBeNull();
    expect(menu.getByRole('link', { name: 'Samsung', hidden: true })).not.toBeVisible();
    // Beside the hero, not above or below it
    expect(nav.closest('aside').nextElementSibling).toBe(
      screen.getByRole('heading', { level: 1 }).closest('section')
    );
  });

  it('sizes the menu column to its categories, not to the hero', async () => {
    mount();

    const nav = await screen.findByRole('navigation', { name: 'კატეგორიები' });
    // jsdom has no layout, so this reads the classes; the screenshots show it
    // drawn. A grid item stretches to its row by default: the column opts out,
    // and the list inside it does not fill the column either
    expect(nav.closest('aside')).toHaveClass('md:self-start');
    expect(nav).not.toHaveClass('h-full');
  });

  it('shows the newest products when no product is flagged or discounted', async () => {
    // What a new shop's API returns: the three groups empty, the fallback filled
    api.getHomeSections.mockResolvedValue({
      newArrivals: [],
      discounted: [],
      featured: [],
      latest: [PRODUCT('anker-nano', 'Anker Nano 20W'), PRODUCT('anker-cable', 'Anker PowerLine')],
      popularCategories: POPULAR,
    });
    mount();

    const section = (await screen.findByRole('heading', { name: HOME_SECTION_TITLES.latest })).closest('section');
    expect(within(section).getByRole('link', { name: /Anker Nano 20W/ })).toHaveAttribute(
      'href',
      '/product/anker-nano'
    );
    expect(within(section).getByRole('link', { name: /Anker PowerLine/ })).toBeInTheDocument();
  });

  it('shows no product and does not break with an empty catalog', async () => {
    api.getHomeSections.mockResolvedValue({
      newArrivals: [],
      discounted: [],
      featured: [],
      latest: [],
      popularCategories: [],
    });
    mount();

    // Loaded: the category grid's skeletons are gone and the page is still there
    await screen.findByRole('heading', { name: HOME_SECTION_TITLES.popularCategories });
    await waitFor(() => expect(document.querySelector('.animate-shimmer')).toBeNull());
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: HOME_SECTION_TITLES.latest })).toBeNull();
    expect(document.querySelector('a[href^="/product/"]')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
