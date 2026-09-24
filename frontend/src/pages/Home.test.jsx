/**
 * The home page's category grid shows top-level categories only. A
 * subcategory's products are already counted in its parent's card, so a card
 * of its own beside the parent would be both misplaced and counted twice.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import Home from './Home.jsx';
import * as api from '../services/api.js';

const POPULAR = [
  { id: 'c-phones', slug: 'phones', name: 'ტელეფონები', icon: 'Smartphone', parentId: null, productsCount: 4 },
  { id: 'c-samsung', slug: 'samsung', name: 'Samsung', icon: 'Smartphone', parentId: 'c-phones', productsCount: 1 },
  { id: 'c-cables', slug: 'cables', name: 'კაბელები', icon: 'Cable', parentId: null, productsCount: 2 },
];

afterEach(() => vi.restoreAllMocks());

describe('Home', () => {
  it('shows root categories in the grid and no subcategory', async () => {
    vi.spyOn(api, 'getHomeSections').mockResolvedValue({
      newArrivals: [],
      discounted: [],
      featured: [],
      popularCategories: POPULAR,
    });

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    );

    expect(await screen.findByRole('link', { name: /ტელეფონები/ })).toHaveAttribute(
      'href',
      '/category/phones'
    );
    expect(screen.getByRole('link', { name: /კაბელები/ })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Samsung/ })).toBeNull();
  });
});
