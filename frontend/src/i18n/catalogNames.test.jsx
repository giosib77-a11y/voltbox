/**
 * Names from the catalogue on an English page.
 *
 * What it covers: the shop at an /en address, over the real http layer, asks
 * for English and shows what comes back - a product's name, its brand, its
 * category in the breadcrumb, and the category and brand options of the search
 * filters. Brand filter values stay the brand's own name, which the URL
 * carries, and only their labels are English.
 * Where it fits: beside language.test.jsx, which covers the interface's words;
 * these are the database's. The API side of the same contract - English where
 * there is some, Georgian where not, Georgian without `lang` - is pinned in
 * backend/tests/test_catalog_language.py; the fake below answers that way.
 * Notes: English only. The categories are cached for the life of a page, and a
 * page never changes language (index.js), so a Georgian render here would read
 * the English cache - something no browser can do. What a Georgian page sends
 * is pinned exactly in services/httpApi.test.js.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router';

import { appRoutes } from '../routes.jsx';
import { ToastProvider } from '../context/ToastContext.jsx';
import { AuthProvider } from '../context/AuthContext.jsx';
import { CartProvider } from '../context/CartContext.jsx';
import { forgetDeliveryRules } from '../hooks/useDeliveryRules.js';
import { basename, i18n } from './index.js';

// The storefront over its real http implementation instead of the mock data.
vi.mock('virtual:api-impl', async () => import('../services/httpApi.js'));

// A lazy page's first import is transformed on demand.
const LAZY_PAGE = 3000;

const category = (en) => ({
  id: '6c0ffee0-0000-4000-8000-000000000001',
  slug: 'headphones',
  name: en ? 'Headphones' : 'ყურსასმენები',
  shortName: en ? 'Headphones' : 'ყურსასმენები',
  description: '',
  icon: 'Headphones',
  parentId: null,
  filters: [{ key: 'brand', label: 'ბრენდი', type: 'checkbox' }],
  productsCount: 1,
});

const product = (en) => ({
  id: 'p-1',
  slug: 'earbuds-pro',
  name: en ? 'Wireless Earbuds Pro' : 'უსადენო ყურსასმენი Pro',
  brand: en ? 'Hoco' : 'ჰოკო',
  brandCountry: null,
  category: 'headphones',
  shortDescription: '',
  description: en ? 'Noise cancelling.' : 'ხმის ჩახშობა.',
  price: '199.00',
  oldPrice: null,
  rating: '0.0',
  reviewsCount: 0,
  stock: 5,
  isNew: false,
  isFeatured: false,
  images: [],
  specs: {},
  tags: [],
  createdAt: '2026-01-01T00:00:00Z',
  discountPercent: 0,
  hasDiscount: false,
  inStock: true,
  isLowStock: false,
});

/** The API as backend/tests/test_catalog_language.py pins it. */
function answer(url) {
  const { pathname, searchParams } = new URL(url, 'http://api');
  const en = searchParams.get('lang') === 'en';
  switch (pathname) {
    case '/api/v1/categories':
      return [category(en)];
    case '/api/v1/products/earbuds-pro':
      return product(en);
    case '/api/v1/products/p-1/related':
      return [];
    case '/api/v1/delivery':
      return { cities: [], freeFrom: '100.00', currency: 'GEL', features: { email: false } };
    case '/api/v1/products':
      return {
        items: [product(en)],
        total: 1,
        page: 1,
        totalPages: 1,
        limit: 12,
        facets: {
          values: { category: { headphones: 1 }, brand: { ჰოკო: 1 } },
          labels: en ? { brand: { ჰოკო: 'Hoco' } } : {},
          price: { min: 199, max: 199, currentMin: 199, currentMax: 199 },
        },
      };
    default:
      return null;
  }
}

let requested = [];

beforeEach(() => {
  forgetDeliveryRules();
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  requested = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      requested.push(url);
      const body = answer(url);
      return body === null
        ? { ok: false, status: 404, json: async () => ({ error: { code: 'NOT_FOUND' } }) }
        : { ok: true, status: 200, json: async () => body };
    }),
  );
});

afterEach(() => {
  i18n.changeLanguage('ka');
  vi.unstubAllGlobals();
});

/** The shop at an English address, the way a page load opens it. */
function openInEnglish(path) {
  i18n.changeLanguage('en');
  const router = createMemoryRouter(appRoutes('en'), {
    basename: basename('en'),
    initialEntries: [`/en${path}`],
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
}

/** Every catalogue request the page made - each must have asked for English. */
const catalogueRequests = () =>
  requested.filter((url) => /\/api\/v1\/(products|categories|search|home-sections)/.test(url));

describe('an English page', () => {
  it("shows a product's English name, its brand's and its category's", async () => {
    openInEnglish('/product/earbuds-pro');

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Wireless Earbuds Pro' }, { timeout: LAZY_PAGE }),
    ).toBeInTheDocument();
    expect(screen.getByText('Hoco')).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Headphones' })).toHaveAttribute(
      'href',
      '/en/category/headphones',
    );
    expect(document.body).not.toHaveTextContent('უსადენო ყურსასმენი');

    expect(catalogueRequests().length).toBeGreaterThan(0);
    for (const url of catalogueRequests()) expect(url).toContain('lang=en');
  });

  it('labels the search filters in English and keeps their values', async () => {
    openInEnglish('/search?q=earbuds&category=headphones&brand=%E1%83%B0%E1%83%9D%E1%83%99%E1%83%9D');

    const sidebar = await screen.findByRole('complementary', {}, { timeout: LAZY_PAGE });
    // The category by its name, not its slug, and the brand by its English name.
    expect(await within(sidebar).findByText('Headphones')).toBeInTheDocument();
    expect(within(sidebar).getByText('Hoco')).toBeInTheDocument();
    expect(within(sidebar).getByRole('checkbox', { name: /Hoco/ })).toBeChecked();

    // The chips above the results read the same labels.
    expect(screen.getByRole('button', { name: /Hoco/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Headphones/ })).toBeInTheDocument();

    // ჰოკო is still the value - in the request, as in the address - and never text.
    const listing = catalogueRequests().find((url) => url.includes('/products?'));
    expect(new URL(listing, 'http://api').searchParams.get('brand')).toBe('ჰოკო');
    expect(document.body).not.toHaveTextContent('ჰოკო');
  });

  it("labels a category page's brand filter in English", async () => {
    openInEnglish('/category/headphones?brand=%E1%83%B0%E1%83%9D%E1%83%99%E1%83%9D');

    const sidebar = await screen.findByRole('complementary', {}, { timeout: LAZY_PAGE });
    expect(await within(sidebar).findByRole('checkbox', { name: /Hoco/ })).toBeChecked();
    expect(screen.getByRole('button', { name: /Hoco/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Headphones' })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent('ჰოკო');
  });
});
