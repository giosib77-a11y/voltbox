/**
 * The home page's category grid shows top-level categories only. A
 * subcategory's products are already counted in its parent's card, so a card
 * of its own beside the parent would be both misplaced and counted twice.
 *
 * Beside the hero, the vertical category menu lists the same roots, with the
 * subcategories in their flyouts.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { HOME_SECTION_TITLES } from '../constants/index.js';

import Home from './Home.jsx';
import * as api from '../services/api.js';

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
});
