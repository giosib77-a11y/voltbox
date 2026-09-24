/**
 * The header's category dropdown: opens on hover and keyboard focus, closes on
 * Escape, and a category without children has no toggle and no panel.
 *
 * The categories are the flat list `/categories` returns; the tree is built
 * from `parentId` by categoryTree, so these also check that a child is shown
 * under its parent and not beside it.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider, createMemoryRouter } from 'react-router';

import CategoryNav, { CAN_HOVER } from './CategoryNav.jsx';

const CATEGORIES = [
  { id: 'c-phones', slug: 'phones', name: 'ტელეფონები', parentId: null },
  { id: 'c-cases', slug: 'cases', name: 'ქეისები', parentId: 'c-phones' },
  { id: 'c-glass', slug: 'glass', name: 'დამცავი მინები', parentId: 'c-phones' },
  { id: 'c-cables', slug: 'cables', name: 'კაბელები', parentId: null },
];

function mount() {
  const router = createMemoryRouter(
    [
      { path: '/', element: <CategoryNav categories={CATEGORIES} /> },
      { path: '/category/:slug', element: <p>category page</p> },
    ],
    { initialEntries: ['/'] }
  );
  render(<RouterProvider router={router} />);
  return router;
}

const phonesLink = () => screen.getByRole('link', { name: 'ტელეფონები' });
const phonesToggle = () => screen.getByRole('button', { name: 'ტელეფონები — ქვეკატეგორიები' });

describe('CategoryNav', () => {
  it('shows a child under its parent, not beside it', () => {
    mount();

    expect(screen.queryByRole('link', { name: 'ქეისები' })).toBeNull();
    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'false');
    // A disclosure, not an ARIA menu: no arrow-key handling, so no haspopup
    expect(phonesToggle()).not.toHaveAttribute('aria-haspopup');
    const panel = document.getElementById(phonesToggle().getAttribute('aria-controls'));
    expect(panel).not.toBeNull();
    expect(panel).not.toBeVisible();
    expect(panel).toContainElement(screen.getByRole('link', { name: 'ქეისები', hidden: true }));
  });

  it('opens on hover and closes when the pointer leaves', async () => {
    const user = userEvent.setup();
    mount();

    await user.hover(phonesLink());

    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('link', { name: 'ქეისები' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'დამცავი მინები' })).toBeInTheDocument();

    await user.unhover(phonesLink());

    expect(screen.queryByRole('link', { name: 'ქეისები' })).toBeNull();
  });

  it('opens on keyboard focus and keeps the children reachable by Tab', async () => {
    const user = userEvent.setup();
    mount();

    await user.tab();
    expect(phonesLink()).toHaveFocus();
    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'true');

    await user.tab();
    expect(phonesToggle()).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('link', { name: 'ქეისები' })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('link', { name: 'დამცავი მინები' })).toHaveFocus();

    // Tab past the last child leaves the item, and the panel goes with it
    await user.tab();
    expect(screen.getByRole('link', { name: 'კაბელები' })).toHaveFocus();
    expect(screen.queryByRole('link', { name: 'ქეისები' })).toBeNull();
  });

  it('closes on Escape and hands focus back to the toggle', async () => {
    const user = userEvent.setup();
    mount();

    await user.tab();
    await user.tab();
    await user.tab();
    expect(screen.getByRole('link', { name: 'ქეისები' })).toHaveFocus();

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('link', { name: 'ქეისები' })).toBeNull();
    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'false');
    expect(phonesToggle()).toHaveFocus();
  });

  it('gives a category without children no toggle and no panel', async () => {
    const user = userEvent.setup();
    mount();

    const cables = screen.getByRole('link', { name: 'კაბელები' });
    await user.hover(cables);
    act(() => cables.focus());

    expect(screen.queryByRole('button', { name: /კაბელები/ })).toBeNull();
    expect(cables.closest('li').querySelector('ul')).toBeNull();
    expect(cables.closest('li').querySelector('[aria-expanded]')).toBeNull();
  });

  it('a tap on the parent goes to its page without opening the panel', async () => {
    const router = mount();

    // A touch tap: pointerdown moves focus before the click lands
    fireEvent.pointerDown(phonesLink(), { pointerType: 'touch' });
    act(() => phonesLink().focus());
    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(phonesLink());

    expect(router.state.location.pathname).toBe('/category/phones');
  });
});

// jsdom has no matchMedia; each test says which pointer the device has
function stubPointer({ canHover }) {
  vi.stubGlobal('matchMedia', (query) => ({
    matches: canHover && query === CAN_HOVER,
    media: query,
    addEventListener() {},
    removeEventListener() {},
  }));
}

describe('CategoryNav, arrow by pointer type', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('hides the arrow where the device can hover, and the link carries the state', async () => {
    stubPointer({ canHover: true });
    const user = userEvent.setup();
    mount();

    expect(screen.queryByRole('button', { name: /ქვეკატეგორიები/ })).toBeNull();
    expect(phonesLink()).toHaveAttribute('aria-expanded', 'false');
    expect(document.getElementById(phonesLink().getAttribute('aria-controls'))).not.toBeNull();

    await user.hover(phonesLink());

    expect(phonesLink()).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('link', { name: 'ქეისები' })).toBeInTheDocument();
  });

  it('keeps the arrow on a device without hover', () => {
    stubPointer({ canHover: false });
    mount();

    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'false');
    expect(phonesLink()).not.toHaveAttribute('aria-expanded');
  });

  it('works from the keyboard without the arrow: focus opens, Escape closes', async () => {
    stubPointer({ canHover: true });
    const user = userEvent.setup();
    mount();

    await user.tab();
    expect(phonesLink()).toHaveFocus();
    expect(phonesLink()).toHaveAttribute('aria-expanded', 'true');

    // No arrow in between: Tab goes from the parent straight to its children
    await user.tab();
    expect(screen.getByRole('link', { name: 'ქეისები' })).toHaveFocus();

    await user.keyboard('{Escape}');

    // Focus comes back to the parent, and coming back does not reopen the panel
    expect(phonesLink()).toHaveFocus();
    expect(phonesLink()).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('link', { name: 'ქეისები' })).toBeNull();

    // Escape with focus on the parent itself closes it too
    await user.tab({ shift: true });
    await user.tab();
    expect(phonesLink()).toHaveAttribute('aria-expanded', 'true');
    await user.keyboard('{Escape}');
    expect(phonesLink()).toHaveFocus();
    expect(phonesLink()).toHaveAttribute('aria-expanded', 'false');
  });
});
