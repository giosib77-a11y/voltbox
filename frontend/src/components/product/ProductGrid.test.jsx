/**
 * Tests for ProductGrid and ProductCarousel - the empty cases.
 *
 * What they cover: what a shop with nothing in it looks like. That is not a
 * hypothetical here: the live database holds zero products until they are
 * entered by hand, so the empty path is the one currently on screen.
 *
 * The carousel's rule is the one worth pinning. It returns null rather than
 * rendering its heading, because a titled rail with nothing under it reads as
 * broken - "ახალი ჩამოსული" above blank space. A grid says "nothing here" on
 * purpose; a home-page section should simply not be there.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { CartProvider } from '../../context/CartContext.jsx';
import { ToastProvider } from '../../context/ToastContext.jsx';
import ProductGrid from './ProductGrid.jsx';
import ProductCarousel from './ProductCarousel.jsx';

const PRODUCT = {
  id: 'a1',
  slug: 'phone',
  name: 'ტელეფონი',
  price: 100,
  oldPrice: null,
  discountPercent: 0,
  inStock: true,
  stock: 3,
  images: ['/images/products/phone.png'],
  brand: 'Samsung',
  rating: 0,
  reviewsCount: 0,
};

/** ProductCard links, reads the cart and raises a toast on add. */
const wrap = (ui) =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <CartProvider>{ui}</CartProvider>
      </ToastProvider>
    </MemoryRouter>,
  );

/** The skeletons shimmer rather than pulse; see components/common/Skeleton.jsx. */
const skeletons = (container) => container.querySelectorAll('.animate-shimmer');

describe('ProductGrid', () => {
  it('renders the products it is given', () => {
    wrap(<ProductGrid products={[PRODUCT]} />);

    expect(screen.getByText('ტელეფონი')).toBeInTheDocument();
  });

  it('says so when there is nothing to show', () => {
    wrap(<ProductGrid products={[]} emptyProps={{ title: 'პროდუქტი არ მოიძებნა' }} />);

    expect(screen.getByText('პროდუქტი არ მოიძებნა')).toBeInTheDocument();
  });

  it('shows skeletons while loading rather than the empty state', () => {
    // Loading is checked before emptiness on purpose: an empty array during the
    // first fetch is "not yet", not "none".
    const { container } = wrap(<ProductGrid products={[]} loading skeletonCount={4} />);

    expect(screen.queryByText(/არ მოიძებნა/)).not.toBeInTheDocument();
    expect(skeletons(container).length).toBeGreaterThan(0);
  });

  it('offers a retry when the request failed', () => {
    const error = new Error('network');
    wrap(<ProductGrid products={[]} error={error} onRetry={() => {}} />);

    expect(screen.getByRole('button')).toBeInTheDocument();
  });
});

describe('ProductCarousel', () => {
  it('renders its heading and products when it has some', () => {
    wrap(<ProductCarousel title="ახალი ჩამოსული" products={[PRODUCT]} />);

    expect(screen.getByText('ახალი ჩამოსული')).toBeInTheDocument();
    expect(screen.getByText('ტელეფონი')).toBeInTheDocument();
  });

  it('disappears entirely when it has none', () => {
    // Not an empty state: a heading with nothing under it reads as broken, and
    // the home page has two more sections that may be in the same position.
    const { container } = wrap(<ProductCarousel title="ახალი ჩამოსული" products={[]} />);

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText('ახალი ჩამოსული')).not.toBeInTheDocument();
  });

  it('still shows its heading while loading', () => {
    // Otherwise the section would pop into existence after the fetch, moving
    // everything below it down the page.
    wrap(<ProductCarousel title="ახალი ჩამოსული" products={[]} loading />);

    expect(screen.getByText('ახალი ჩამოსული')).toBeInTheDocument();
  });
});

const renderGrid = (products) =>
  render(
    <ToastProvider>
      <CartProvider>
        <MemoryRouter>
          <ProductGrid products={products} />
        </MemoryRouter>
      </CartProvider>
    </ToastProvider>,
  );

describe('what loads first', () => {
  it('does not make the top of the page wait for a lazy image', async () => {
    // Every image on the site was lazy, the one at the top of the home page
    // included. A lazy image starts downloading only after layout, so the
    // largest thing on the first screen waited for a round trip it did not
    // need to.
    renderGrid([...Array(8)].map((_, i) => ({ ...PRODUCT, id: `p${i}` })));

    const images = screen.getAllByRole('img');
    expect(images.slice(0, 4).map((img) => img.getAttribute('loading'))).toEqual([
      'eager',
      'eager',
      'eager',
      'eager',
    ]);
  });

  it('leaves everything below the fold lazy', async () => {
    renderGrid([...Array(8)].map((_, i) => ({ ...PRODUCT, id: `p${i}` })));

    const images = screen.getAllByRole('img');
    expect(images.slice(4).every((img) => img.getAttribute('loading') === 'lazy')).toBe(true);
  });
});
