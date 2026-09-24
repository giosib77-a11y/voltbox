/**
 * The vertical category menu: a root's subcategories open in a flyout to the
 * right of the list, on hover and keyboard focus; Escape closes it, and a
 * category without children has no toggle and no panel.
 *
 * The categories are the flat list `/categories` returns; the tree is built
 * from `parentId` by categoryTree, so these also check that a child is shown
 * under its parent and not beside it.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider, createMemoryRouter } from 'react-router';

import CategoryNav, { AIM_MS, CAN_HOVER } from './CategoryNav.jsx';

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

  it('opens on hover and closes a moment after the pointer leaves', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mount();

    await user.hover(phonesLink());

    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('link', { name: 'ქეისები' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'დამცავი მინები' })).toBeInTheDocument();

    await user.unhover(phonesLink());
    act(() => vi.advanceTimersByTime(AIM_MS));

    expect(screen.queryByRole('link', { name: 'ქეისები' })).toBeNull();
    vi.useRealTimers();
  });

  it('opens the flyout to the right of the list, as tall as the list', async () => {
    const user = userEvent.setup();
    mount();

    await user.hover(phonesLink());

    const panel = document.getElementById(phonesToggle().getAttribute('aria-controls'));
    expect(panel).toBeVisible();
    expect(panel).toContainElement(screen.getByRole('link', { name: 'ქეისები' }));
    expect(panel).toContainElement(screen.getByRole('link', { name: 'დამცავი მინები' }));
    // jsdom has no layout, so the side is read from the classes; the screenshots
    // show it drawn. Beside the list, from its top, and not below the row
    expect(panel).toHaveClass('left-full', 'top-0', 'min-h-full');
    expect(panel).not.toHaveClass('top-full');
    // Positioned against the list, not the row, so it spans the list's height
    expect(panel.closest('li')).not.toHaveClass('relative');
    expect(panel.closest('nav')).toHaveClass('relative');
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

/**
 * A pointer on its way to the flyout crosses the rows below its own. Moving
 * right, a row it crosses waits AIM_MS before taking over, and reaching the
 * panel cancels the switch; moving straight down switches at once.
 */
describe('CategoryNav, pointer on its way to the flyout', () => {
  afterEach(() => vi.useRealTimers());

  const cablesLink = () => screen.getByRole('link', { name: 'კაბელები' });
  const casesLink = () => screen.getByRole('link', { name: 'ქეისები' });

  async function openPhonesAt(user, clientX) {
    await user.pointer({ target: phonesLink(), coords: { clientX, clientY: 10 } });
    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'true');
  }

  it('keeps the flyout open while the pointer crosses a row diagonally', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mount();
    await openPhonesAt(user, 40);

    // Down and to the right, across the next row
    await user.pointer({ target: cablesLink(), coords: { clientX: 120, clientY: 50 } });
    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'true');

    // ...and on into the flyout, before the row's wait is over
    act(() => vi.advanceTimersByTime(AIM_MS / 2));
    await user.pointer({ target: casesLink(), coords: { clientX: 260, clientY: 60 } });
    act(() => vi.advanceTimersByTime(AIM_MS * 2));

    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'true');
    expect(casesLink()).toBeVisible();
  });

  it('hands over to the crossed row if the pointer stops there', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mount();
    await openPhonesAt(user, 40);

    await user.pointer({ target: cablesLink(), coords: { clientX: 120, clientY: 50 } });
    act(() => vi.advanceTimersByTime(AIM_MS));

    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'false');
  });

  it('switches at once when the pointer moves straight down', async () => {
    const user = userEvent.setup();
    mount();
    await openPhonesAt(user, 40);

    await user.pointer({ target: cablesLink(), coords: { clientX: 40, clientY: 50 } });

    expect(phonesToggle()).toHaveAttribute('aria-expanded', 'false');
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
