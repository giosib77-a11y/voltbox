import { Star } from 'lucide-react';
import { formatNumber, formatRating, formatReviews } from '../../utils/format.js';

/**
 * ვარსკვლავები ნახევრების მხარდაჭერით.
 *
 * A product nobody has reviewed renders nothing at all. Five empty stars and
 * "(0)" is not the absence of a rating - it reads as a rating of zero, and
 * every product the shop adds would launch looking badly reviewed. There is no
 * reviews table yet, so this is the honest answer until there is one.
 *
 * `reviewsCount = null` still means "show the stars, no count" - for callers
 * that have a rating from somewhere other than a review count.
 *
 * @param {{ rating:number, reviewsCount?:number, size?:'sm'|'md'|'lg',
 *            showValue?:boolean, showReviewsLabel?:boolean }} props
 */

const SIZES = {
  sm: { star: 'h-3.5 w-3.5', text: 'text-xs' },
  md: { star: 'h-4 w-4', text: 'text-sm' },
  lg: { star: 'h-5 w-5', text: 'text-base' },
};

export default function RatingStars({
  rating = 0,
  reviewsCount = null,
  size = 'sm',
  showValue = false,
  showReviewsLabel = false,
  className = '',
}) {
  const dims = SIZES[size] || SIZES.sm;

  // Nobody has rated this yet. Say nothing rather than something untrue.
  if (reviewsCount === 0) return null;

  const clamped = Math.max(0, Math.min(5, Number(rating) || 0));
  const percent = (clamped / 5) * 100;

  const label =
    reviewsCount === null
      ? `შეფასება ${formatRating(clamped)} ხუთიდან`
      : `შეფასება ${formatRating(clamped)} ხუთიდან, ${formatNumber(reviewsCount)} შეფასების საფუძველზე`;

  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <div className="relative inline-flex" role="img" aria-label={label}>
        <div className="flex gap-0.5">
          {[0, 1, 2, 3, 4].map((i) => (
            <Star key={i} className={`${dims.star} text-ink-300`} fill="currentColor" aria-hidden="true" />
          ))}
        </div>
        <div
          className="absolute inset-0 overflow-hidden"
          style={{ width: `${percent}%` }}
          aria-hidden="true"
        >
          <div className="flex gap-0.5">
            {[0, 1, 2, 3, 4].map((i) => (
              <Star key={i} className={`${dims.star} shrink-0 text-accent-400`} fill="currentColor" />
            ))}
          </div>
        </div>
      </div>

      {showValue && (
        <span className={`font-semibold text-ink-800 ${dims.text}`}>{formatRating(clamped)}</span>
      )}
      {reviewsCount !== null && (
        <span className={`text-ink-500 ${dims.text}`}>
          {showReviewsLabel ? formatReviews(reviewsCount) : `(${formatNumber(reviewsCount)})`}
        </span>
      )}
    </div>
  );
}
