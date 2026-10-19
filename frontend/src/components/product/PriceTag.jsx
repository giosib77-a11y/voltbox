import { formatDiscount, formatPrice } from '../../utils/format.js';
import Badge from '../common/Badge.jsx';

/**
 * ფასის ბლოკი: მიმდინარე ფასი + გადახაზული ძველი + ფასდაკლების ბეჯი.
 */

const SIZES = {
  sm: { price: 'text-lg font-medium sm:text-xl', old: 'text-xs' },
  md: { price: 'text-[22px] font-medium sm:text-[26px]', old: 'text-[13px] sm:text-[15px]' },
  lg: { price: 'text-[30px] font-semibold sm:text-[40px]', old: 'text-[13px] sm:text-[15px]' },
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
      <span className={`font-display leading-[1.1] lining-nums text-ink-900 ${dims.price}`}>
        {formatPrice(price)}
      </span>

      {hasDiscount && (
        <span className={`tabular-nums text-ink-500 line-through ${dims.old}`}>{formatPrice(oldPrice)}</span>
      )}

      {hasDiscount && showBadge && discountPercent > 0 && (
        <Badge tone="discount" size="sm">
          {formatDiscount(discountPercent)}
        </Badge>
      )}
    </div>
  );
}
