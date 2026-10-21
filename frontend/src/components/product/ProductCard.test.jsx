/**
 * ProductCard keyboard focus.
 *
 * The card is `overflow-hidden`, and the global focus ring is an outer
 * box-shadow, so a ring drawn outside the main link is clipped away and only a
 * sliver survives (WCAG 2.4.7). The link therefore draws its ring inset.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { CartProvider } from '../../context/CartContext.jsx';
import { ToastProvider } from '../../context/ToastContext.jsx';
import ProductCard from './ProductCard.jsx';

const PRODUCT = {
  id: 'a1',
  slug: 'phone',
  name: 'Phone',
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

const renderCard = () =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <CartProvider>
          <ProductCard product={PRODUCT} />
        </CartProvider>
      </ToastProvider>
    </MemoryRouter>,
  );

describe('ProductCard focus ring', () => {
  it('draws the main link ring inside the clipped card, with no offset', () => {
    renderCard();

    const classes = screen.getByRole('link', { name: 'Phone' }).className.split(/\s+/);
    expect(classes).toContain('focus-visible:ring-2');
    expect(classes).toContain('focus-visible:ring-inset');
    expect(classes).toContain('focus-visible:ring-primary-500');
    // The global rule adds ring-offset-2, which would push an inset ring's gap
    // outside the box again.
    expect(classes).toContain('focus-visible:ring-offset-0');
  });
});
