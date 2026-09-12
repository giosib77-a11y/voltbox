/**
 * Tests for RatingStars.
 *
 * What they cover: the one case the component used to get wrong. A product with
 * no reviews rendered five empty stars and "(0)", which is not "not rated yet" -
 * it reads as a rating of zero, and every product the shop adds would launch
 * looking badly reviewed. There is no reviews table, so nothing can ever
 * correct it either.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import RatingStars from './RatingStars.jsx';

describe('RatingStars', () => {
  it('renders nothing for a product nobody has reviewed', () => {
    const { container } = render(<RatingStars rating={0} reviewsCount={0} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('says nothing even if a rating arrives without any reviews behind it', () => {
    // Seeded data can carry a rating with a zero count. The count is what says
    // whether anyone actually rated it.
    const { container } = render(<RatingStars rating={4.5} reviewsCount={0} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('shows the rating once there are reviews', () => {
    render(<RatingStars rating={4.5} reviewsCount={12} showValue />);

    expect(screen.getByRole('img', { name: /4[.,]5/ })).toBeInTheDocument();
    expect(screen.getByText('(12)')).toBeInTheDocument();
  });

  it('still shows stars alone when no count is given', () => {
    // `null` means "no count to display", which is not the same as "no reviews".
    render(<RatingStars rating={3} reviewsCount={null} />);

    expect(screen.getByRole('img', { name: /შეფასება/ })).toBeInTheDocument();
    expect(screen.queryByText('(0)')).not.toBeInTheDocument();
  });
});
