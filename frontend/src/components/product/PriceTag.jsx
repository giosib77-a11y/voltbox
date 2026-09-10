import { formatDiscount, formatPrice } from '../../utils/format.js';
import Badge from '../common/Badge.jsx';

/**
 * ფასის ბლოკი: მიმდინარე ფასი + გადახაზული ძველი + ფასდაკლების ბეჯი.
 */

const SIZES = {
  sm: { price: 'text-base', old: 'text-xs' },
  md: { price: 'text-lg', old: 'text-sm' },
  lg: { price: 'text-3xl', old: 'text-base' },
};

export default function PriceTag({
  price,
  oldPrice = null,
  discountPercent = 0,
  size = 'md',
  showBadge = false,
  className = '',
}) {
  const dims = SIZES[size] || SIZES.md;
  const hasDiscount = Boolean(oldPrice) && oldPrice > price;

  return (
    <div className={`flex flex-wrap items-baseline gap-x-2 gap-y-1 ${className}`}>
      <span className={`font-bold tracking-tight text-ink-900 ${dims.price}`}>
        {formatPrice(price)}
      </span>

      {hasDiscount && (
        <span className={`text-ink-500 line-through ${dims.old}`}>{formatPrice(oldPrice)}</span>
      )}

      {hasDiscount && showBadge && discountPercent > 0 && (
        <Badge tone="discount" size="sm">
          {formatDiscount(discountPercent)}
        </Badge>
      )}
    </div>
  );
}
