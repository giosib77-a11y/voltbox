/**
 * The language in the address: the switch, the links, the document's head.
 *
 * What it covers: the shop's own route table (routes.jsx) mounted the way
 * App.jsx mounts it - Georgian at the bare path, English under the basename
 * /en - so a link that forgets the language, a switch that drops the page, or
 * an English page that names itself in Georgian fails here.
 * Where it fits: beside i18n.test.js, which checks the words; this checks
 * where they are served.
 * Notes: a memory router stands in for the browser one; the routes, Layout,
 * header and footer are the real ones, against the mock API. The language is
 * set before rendering, as a page load sets it - it never changes under a
 * running page (index.js).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider, createMemoryRouter } from 'react-router';

import { appRoutes } from '../routes.jsx';
import { ToastProvider } from '../context/ToastContext.jsx';
import { AuthProvider } from '../context/AuthContext.jsx';
import { CartProvider } from '../context/CartContext.jsx';
import { forgetDeliveryRules } from '../hooks/useDeliveryRules.js';
import { loginRedirectTarget } from '../services/session.js';
import { basename, i18n, languageFromPath, localizedPath, stripLanguage } from './index.js';

// A lazy page's first import is transformed on demand.
const LAZY_PAGE = 3000;

beforeEach(() => {
  forgetDeliveryRules();
  // ScrollToTop runs on every navigation; jsdom does not implement scrolling
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
});

afterEach(() => {
  document.head.querySelectorAll('link[rel="alternate"]').forEach((link) => link.remove());
});

/** The shop at `url`, in the language the address is in. */
function open(url) {
  const language = languageFromPath(url);
  i18n.changeLanguage(language);
  const router = createMemoryRouter(appRoutes(language), {
    basename: basename(language) || '/',
    initialEntries: [url],
  });
  render(
    <ToastProvider>
      <AuthProvider>
        <CartProvider>
          <RouterProvider router={router} />
        </CartProvider>
      </AuthProvider>
    </ToastProvider>,
  );
  return router;
}

/**
 * Every link on the page to somewhere in the shop. The language switch is
 * left out - leaving the language is its job - and so is the admin panel,
 * which is Georgian only.
 */
function shopLinks() {
  return [...document.querySelectorAll('a[href^="/"]')]
    .filter((a) => !a.hasAttribute('hreflang'))
    .map((a) => a.getAttribute('href'))
    .filter((href) => !href.startsWith('/admin'));
}

const alternate = (hreflang) =>
  document.head.querySelector(`link[rel="alternate"][hreflang="${hreflang}"]`)?.getAttribute('href');

describe('the address carries the language', () => {
  it('reads it from the first segment, and only that', () => {
    expect(languageFromPath('/en')).toBe('en');
    expect(languageFromPath('/en/cart')).toBe('en');
    expect(languageFromPath('/cart')).toBe('ka');
    expect(languageFromPath('/english')).toBe('ka');
    expect(stripLanguage('/en/product/x')).toBe('/product/x');
    expect(stripLanguage('/en')).toBe('/');
    expect(localizedPath('/', 'en')).toBe('/en');
    expect(localizedPath('/cart', 'ka')).toBe('/cart');
  });
});

describe('a Georgian address', () => {
  it('still opens the page it always did, in Georgian', async () => {
    const router = open('/cart');

    expect(
      await screen.findByText('თქვენი კალათა ცარიელია', {}, { timeout: LAZY_PAGE }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/cart');
    expect(document.documentElement.lang).toBe('ka');
    expect(shopLinks().filter((href) => href === '/en' || href.startsWith('/en/'))).toEqual([]);
  });

  it('offers the same page in English', async () => {
    open('/cart?from=header#top');
    await screen.findByText('თქვენი კალათა ცარიელია', {}, { timeout: LAZY_PAGE });

    const header = screen.getByRole('banner');
    const toEnglish = within(header).getByRole('link', { name: 'ინგლისურ ენაზე გადართვა' });
    expect(toEnglish).toHaveAttribute('href', '/en/cart?from=header#top');
    expect(toEnglish).toHaveTextContent('ქარ');
  });
});

describe('an English address', () => {
  it('is the same page in English', async () => {
    const router = open('/en/cart');

    expect(await screen.findByText('Your cart is empty', {}, { timeout: LAZY_PAGE })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/en/cart');
    expect(document.documentElement.lang).toBe('en');
  });

  it('keeps every link in the shop in English', async () => {
    open('/en/cart');
    await screen.findByText('Your cart is empty', {}, { timeout: LAZY_PAGE });

    const links = shopLinks();
    // logo, cart, sign-in, breadcrumb, the empty cart's way back, the footer
    expect(links.length).toBeGreaterThan(5);
    expect(links.filter((href) => href !== '/en' && !href.startsWith('/en/'))).toEqual([]);
  });

  it('stays in English when a link is followed', async () => {
    const user = userEvent.setup();
    const router = open('/en/cart');
    await screen.findByText('Your cart is empty', {}, { timeout: LAZY_PAGE });

    const footer = screen.getByRole('navigation', { name: 'Information' });
    await user.click(within(footer).getByRole('link', { name: 'Delivery terms' }));

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Delivery terms' }, { timeout: LAZY_PAGE }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/en/delivery');
    expect(shopLinks().filter((href) => href !== '/en' && !href.startsWith('/en/'))).toEqual([]);
  }, 10_000);

  it('switches back to the same page in Georgian', async () => {
    open('/en/search?q=usb#results');

    // The header is not lazy, so there is no page chunk to wait for.
    const toGeorgian = await within(await screen.findByRole('banner')).findByRole('link', {
      name: 'Switch to Georgian',
    });
    expect(toGeorgian).toHaveAttribute('href', '/search?q=usb#results');
    expect(toGeorgian).toHaveAttribute('hreflang', 'ka');
    // It shows the language the page is in; its name says where it goes.
    expect(toGeorgian).toHaveTextContent('ENG');
  });

  it('names both versions of the page, and itself', async () => {
    open('/en/cart');
    await screen.findByText('Your cart is empty', {}, { timeout: LAZY_PAGE });

    expect(alternate('ka')).toMatch(/(^|[^n])\/cart$/);
    expect(alternate('ka')).not.toContain('/en/');
    expect(alternate('en')).toMatch(/\/en\/cart$/);
    expect(alternate('x-default')).toBe(alternate('ka'));
  });

  it('answers an unknown path with the not-found page, in English', async () => {
    open('/en/no-such-page');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Page not found' }, { timeout: LAZY_PAGE }),
    ).toBeInTheDocument();
  });

  it('has no admin panel: that is Georgian only', async () => {
    open('/en/admin');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Page not found' }, { timeout: LAZY_PAGE }),
    ).toBeInTheDocument();
  });
});

describe('a lost session', () => {
  it('sends an English shopper to the English sign-in, and back to the same page', () => {
    expect(loginRedirectTarget('/en/account/orders', '?page=2')).toBe(
      `/en/login?redirect=${encodeURIComponent('/account/orders?page=2')}`,
    );
  });

  it('sends a Georgian shopper where it always did', () => {
    expect(loginRedirectTarget('/account/orders', '')).toBe(
      `/login?redirect=${encodeURIComponent('/account/orders')}`,
    );
    expect(loginRedirectTarget('/admin/orders', '')).toBe(
      `/admin/login?next=${encodeURIComponent('/admin/orders')}`,
    );
  });

  it('does not loop on the sign-in page, in either language', () => {
    expect(loginRedirectTarget('/login')).toBeNull();
    expect(loginRedirectTarget('/en/login')).toBeNull();
    expect(loginRedirectTarget('/admin/login')).toBeNull();
  });
});
