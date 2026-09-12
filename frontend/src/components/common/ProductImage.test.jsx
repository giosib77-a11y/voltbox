/**
 * Tests for ProductImage.
 *
 * What they cover: the fallback chain, which is the part that fails silently.
 * A product image can go missing for reasons nobody controls - a deleted file,
 * a storage outage, a URL frozen into an old order - and the component has two
 * jobs then: show something, and stop pretending it is still loading.
 *
 * The second one is the subtle half. The skeleton is driven by state, so if the
 * fallback image also fails to load, nothing would ever clear it and the card
 * would pulse forever on a page that has finished.
 */

import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import ProductImage from './ProductImage.jsx';

const FALLBACK = '/images/placeholder.svg';

describe('ProductImage', () => {
  it('shows the image it was given', () => {
    render(<ProductImage src="/images/products/phone.png" alt="ტელეფონი" />);

    expect(screen.getByAltText('ტელეფონი')).toHaveAttribute('src', '/images/products/phone.png');
  });

  it('falls back to the local placeholder when the source fails', () => {
    render(<ProductImage src="https://storage.example/gone.png" alt="ტელეფონი" />);
    const img = screen.getByAltText('ტელეფონი');

    fireEvent.error(img);

    expect(img).toHaveAttribute('src', FALLBACK);
  });

  it('uses the placeholder when there is no source at all', () => {
    render(<ProductImage src={null} alt="ტელეფონი" />);

    expect(screen.getByAltText('ტელეფონი')).toHaveAttribute('src', FALLBACK);
  });

  it('stops pulsing once the image loads', () => {
    const { container } = render(<ProductImage src="/images/products/phone.png" alt="ტელეფონი" />);
    expect(container.querySelector('.animate-pulse')).not.toBeNull();

    fireEvent.load(screen.getByAltText('ტელეფონი'));

    expect(container.querySelector('.animate-pulse')).toBeNull();
  });

  it('stops pulsing even when the placeholder itself fails', () => {
    // The case with no way out: the real image is gone and the fallback cannot
    // load either. Leaving the skeleton up would pulse forever on a page that
    // has finished loading.
    const { container } = render(<ProductImage src="https://storage.example/gone.png" alt="ტ" />);
    const img = screen.getByAltText('ტ');

    fireEvent.error(img); // real image fails -> switches to the placeholder
    expect(img).toHaveAttribute('src', FALLBACK);

    fireEvent.error(img); // the placeholder fails too

    expect(container.querySelector('.animate-pulse')).toBeNull();
  });

  it('goes back to loading when the product changes', () => {
    const { container, rerender } = render(<ProductImage src="/a.png" alt="ტ" />);
    fireEvent.load(screen.getByAltText('ტ'));
    expect(container.querySelector('.animate-pulse')).toBeNull();

    rerender(<ProductImage src="/b.png" alt="ტ" />);

    expect(screen.getByAltText('ტ')).toHaveAttribute('src', '/b.png');
    expect(container.querySelector('.animate-pulse')).not.toBeNull();
  });
});
