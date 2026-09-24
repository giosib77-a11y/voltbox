/**
 * The header's "კატეგორიები" button: on every page but the home page it opens
 * the vertical category menu as a dropdown. On the home page the same menu
 * stands beside the hero, so the header has no button.
 *
 * The header's other controls need the auth and cart providers and are not
 * what these check, so they are stubbed.
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider, createMemoryRouter } from 'react-router';

import Header from './Header.jsx';

vi.mock('./UserMenu.jsx', () => ({ default: () => null }));
vi.mock('./MobileMenu.jsx', () => ({ default: () => null }));
vi.mock('./ThemeToggle.jsx', () => ({ default: () => null }));
vi.mock('../cart/CartBadge.jsx', () => ({ default: () => null }));
vi.mock('../search/SearchBar.jsx', () => ({ default: () => null }));

const CATEGORIES = [
  { id: 'c-phones', slug: 'phones', name: 'ტელეფონები', icon: 'Smartphone', parentId: null },
  { id: 'c-cases', slug: 'cases', name: 'ქეისები', icon: 'Package', parentId: 'c-phones' },
  { id: 'c-cables', slug: 'cables', name: 'კაბელები', icon: 'Cable', parentId: null },
];

function mountAt(path) {
  const router = createMemoryRouter(
    [{ path: '*', element: <Header categories={CATEGORIES} /> }],
    { initialEntries: [path] }
  );
  render(<RouterProvider router={router} />);
  return router;
}

const menuButton = () => screen.getByRole('button', { name: 'კატეგორიები' });
const phonesLink = () => screen.getByRole('link', { name: 'ტელეფონები' });

describe('Header category button', () => {
  it('is not on the home page, where the menu stands beside the hero', () => {
    mountAt('/');

    expect(screen.queryByRole('button', { name: 'კატეგორიები' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'ტელეფონები', hidden: true })).toBeNull();
  });

  it('opens the vertical menu on a category page', async () => {
    const user = userEvent.setup();
    mountAt('/category/cables');

    expect(menuButton()).toHaveAttribute('aria-expanded', 'false');
    const dropdown = document.getElementById(menuButton().getAttribute('aria-controls'));
    expect(dropdown).not.toBeVisible();
    expect(screen.queryByRole('link', { name: 'ტელეფონები' })).toBeNull();

    await user.click(menuButton());

    expect(menuButton()).toHaveAttribute('aria-expanded', 'true');
    expect(dropdown).toBeVisible();
    const nav = screen.getByRole('navigation', { name: 'კატეგორიები' });
    expect(dropdown).toContainElement(nav);
    expect(nav).toContainElement(phonesLink());
    expect(nav).toContainElement(screen.getByRole('link', { name: 'კაბელები' }));

    // The same flyouts as on the home page
    await user.hover(phonesLink());
    expect(screen.getByRole('link', { name: 'ქეისები' })).toBeVisible();
  });

  it('Escape closes the flyout first, then the dropdown, handing focus back each time', async () => {
    const user = userEvent.setup();
    mountAt('/category/cables');

    await user.click(menuButton());
    await user.tab();
    expect(phonesLink()).toHaveFocus();
    await user.tab(); // the arrow (jsdom has no hover)
    await user.tab();
    expect(screen.getByRole('link', { name: 'ქეისები' })).toHaveFocus();

    await user.keyboard('{Escape}');

    expect(menuButton()).toHaveAttribute('aria-expanded', 'true');
    expect(screen.queryByRole('link', { name: 'ქეისები' })).toBeNull();
    expect(screen.getByRole('button', { name: 'ტელეფონები — ქვეკატეგორიები' })).toHaveFocus();

    await user.keyboard('{Escape}');

    expect(menuButton()).toHaveAttribute('aria-expanded', 'false');
    expect(menuButton()).toHaveFocus();
  });

  it('closes when a category is chosen', async () => {
    const user = userEvent.setup();
    const router = mountAt('/category/cables');

    await user.click(menuButton());
    await user.click(phonesLink());

    expect(router.state.location.pathname).toBe('/category/phones');
    expect(menuButton()).toHaveAttribute('aria-expanded', 'false');
  });

  it('closes on a click outside it', async () => {
    const user = userEvent.setup();
    mountAt('/category/cables');

    await user.click(menuButton());
    await user.click(document.body);

    expect(menuButton()).toHaveAttribute('aria-expanded', 'false');
  });
});
