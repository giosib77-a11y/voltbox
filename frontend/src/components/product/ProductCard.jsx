import { memo } from 'react';
import { Link, useNavigate } from 'react-router';
import { Check, ShoppingCart } from 'lucide-react';
import ProductImage from '../common/ProductImage.jsx';
import Badge from '../common/Badge.jsx';
import PriceTag from './PriceTag.jsx';
import RatingStars from './RatingStars.jsx';
import { useCart } from '../../hooks/useCart.js';
import { useToast } from '../../hooks/useToast.js';
import { formatDiscount } from '../../utils/format.js';
import { cartLimitMessage } from '../../utils/cartLimit.js';
import { t } from '../../i18n/index.js';

/**
 * პროდუქტის ბარათი.
 * მთელი ბარათი ბმულია; „კალათაში დამატება“ ბმულს არ ააქტიურებს.
 */
function ProductCard({ product, className = '', priority = false }) {
  const { addItem, quantities } = useCart();
  const toast = useToast();
  const navigate = useNavigate();

  const inCartQty = quantities[product.id] || 0;
  const isOutOfStock = !product.inStock;

  function handleAdd(event) {
    event.preventDefault();
    event.stopPropagation();
    if (isOutOfStock) return;

    const limit = addItem(product, 1);
    if (limit) {
      toast.error(cartLimitMessage(limit));
      return;
    }
    toast.success(t('product.addedNamed', { name: product.name }), {
      action: { label: t('product.viewCart'), onClick: () => navigate('/cart') },
    });
  }

  return (
    <article
      className={`group relative flex h-full flex-col overflow-hidden rounded-card border border-line bg-surface transition-[border-color,box-shadow] duration-200 hover:border-primary-500 hover:shadow-glow ${className}`}
    >
      <Link
        to={`/product/${product.slug}`}
        className="flex flex-1 flex-col focus-visible:outline-none"
        aria-label={product.name}
      >
        {/* The photo tile: full width, no padding, its own contour below
            (DESIGN.md §6). `media` is light in both themes; the photo
            multiplies into it (ProductImage, `storefront:`). */}
        <div className="relative border-b border-line">
          <ProductImage
            src={product.images?.[0]}
            alt={product.name}
            className="aspect-square w-full"
            imgClassName="transition-transform duration-300 group-hover:scale-[1.04]"
            loading={priority ? 'eager' : 'lazy'}
            sizes="(min-width: 1280px) 25vw, (min-width: 640px) 33vw, 50vw"
            shopPlaceholder
          />

          <div className="pointer-events-none absolute left-3 top-3 flex flex-col items-start gap-1.5">
            {/* The tile is light in both themes, so the eyebrow sits on a
                surface chip: gold text straight on the tile fails AA in dark. */}
            {product.isNew && (
              <span className="rounded-control bg-surface px-2 py-1 text-[11px] leading-none tracking-[0.16em] text-primary-700">
                {t('common.isNew')}
              </span>
            )}
            {product.hasDiscount && (
              <Badge tone="discount">{formatDiscount(product.discountPercent)}</Badge>
            )}
          </div>

          {isOutOfStock && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/70 backdrop-blur-[1px]">
              <span className="rounded-pill bg-scrim/85 px-3 py-1.5 text-xs font-semibold text-white">
                {t('common.outOfStock')}
              </span>
            </div>
          )}
        </div>

        <div className="flex flex-1 flex-col gap-2 p-3.5 sm:p-[22px]">
          <p className="font-display text-[11px] font-semibold uppercase leading-[1.3] tracking-[0.22em] text-primary-700 sm:text-[13px] sm:tracking-[0.3em]">
            {product.brand}
          </p>

          <h3 className="line-clamp-2-fallback min-h-[2.8em] font-serif text-[15px] font-normal leading-[1.4] text-fg transition-colors group-hover:text-primary-700 sm:text-lg">
            {product.name}
          </h3>

          <p className="line-clamp-2-fallback text-xs leading-relaxed text-fg-muted">
            {product.shortDescription}
          </p>

          <RatingStars rating={product.rating} reviewsCount={product.reviewsCount} />

          <div className="mt-auto pt-2">
            <PriceTag price={product.price} oldPrice={product.oldPrice} size="md" />
          </div>
        </div>
      </Link>

      <div className="px-3.5 pb-3.5 sm:px-[22px] sm:pb-[22px]">
        <button
          type="button"
          onClick={handleAdd}
          disabled={isOutOfStock}
          aria-label={t('product.addNamed', { name: product.name })}
          className={[
            'inline-flex h-11 w-full items-center justify-center gap-2 whitespace-nowrap rounded-control px-2 text-[13px] transition-colors sm:h-[50px] sm:gap-2.5 sm:text-sm',
            '[font-weight:var(--btn-weight)] [letter-spacing:var(--btn-tracking)]',
            isOutOfStock
              ? 'cursor-not-allowed bg-ink-100 text-ink-500'
              : inCartQty > 0
                ? 'bg-success-50 text-success-700 ring-1 ring-inset ring-success-500/30 hover:bg-success-100'
                : 'bg-primary-600 text-on-primary hover:bg-primary-hover active:bg-primary-press',
          ].join(' ')}
        >
          {isOutOfStock ? (
            t('common.outOfStock')
          ) : inCartQty > 0 ? (
            <>
              <Check className="h-4 w-4" aria-hidden="true" />
              {t('product.inCart', { count: inCartQty })}
            </>
          ) : (
            <>
              <ShoppingCart className="h-[18px] w-[18px]" aria-hidden="true" />
              {t('common.addToCart')}
            </>
          )}
        </button>
      </div>
    </article>
  );
}

export default memo(ProductCard);
