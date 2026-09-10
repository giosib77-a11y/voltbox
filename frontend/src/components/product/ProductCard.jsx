import { memo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Check, ShoppingCart } from 'lucide-react';
import ProductImage from '../common/ProductImage.jsx';
import Badge from '../common/Badge.jsx';
import PriceTag from './PriceTag.jsx';
import RatingStars from './RatingStars.jsx';
import { useCart } from '../../hooks/useCart.js';
import { useToast } from '../../hooks/useToast.js';
import { formatDiscount } from '../../utils/format.js';
import { TEXT } from '../../constants/index.js';

/**
 * პროდუქტის ბარათი.
 * მთელი ბარათი ბმულია; „კალათაში დამატება“ ბმულს არ ააქტიურებს.
 */
function ProductCard({ product, className = '' }) {
  const { addItem, quantities } = useCart();
  const toast = useToast();
  const navigate = useNavigate();

  const inCartQty = quantities[product.id] || 0;
  const isOutOfStock = !product.inStock;

  function handleAdd(event) {
    event.preventDefault();
    event.stopPropagation();
    if (isOutOfStock) return;

    addItem(product, 1);
    toast.success(`${product.name} — ${TEXT.addedToCart}`, {
      action: { label: 'კალათის ნახვა', onClick: () => navigate('/cart') },
    });
  }

  return (
    <article
      className={`group relative flex h-full flex-col overflow-hidden rounded-card border border-ink-200 bg-white transition-all duration-200 hover:-translate-y-0.5 hover:border-ink-300 hover:shadow-card-hover ${className}`}
    >
      <Link
        to={`/product/${product.slug}`}
        className="flex flex-1 flex-col focus-visible:outline-none"
        aria-label={product.name}
      >
        <div className="relative">
          <ProductImage
            src={product.images?.[0]}
            alt={product.name}
            className="aspect-square w-full"
            imgClassName="transition-transform duration-300 group-hover:scale-[1.04]"
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
          />

          <div className="pointer-events-none absolute left-2.5 top-2.5 flex flex-col items-start gap-1.5">
            {product.isNew && <Badge tone="new">{TEXT.isNew}</Badge>}
            {product.hasDiscount && (
              <Badge tone="discount">{formatDiscount(product.discountPercent)}</Badge>
            )}
          </div>

          {isOutOfStock && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/70 backdrop-blur-[1px]">
              <span className="rounded-pill bg-ink-800 px-3 py-1.5 text-xs font-semibold text-white">
                {TEXT.outOfStock}
              </span>
            </div>
          )}
        </div>

        <div className="flex flex-1 flex-col gap-1.5 p-3.5 sm:p-4">
          <p className="text-2xs font-semibold uppercase tracking-wide text-ink-500">{product.brand}</p>

          <h3 className="line-clamp-2-fallback min-h-[2.5rem] text-sm font-semibold leading-tight text-ink-900 transition-colors group-hover:text-primary-700">
            {product.name}
          </h3>

          <p className="line-clamp-2-fallback text-xs leading-relaxed text-ink-500">
            {product.shortDescription}
          </p>

          <RatingStars rating={product.rating} reviewsCount={product.reviewsCount} className="mt-0.5" />

          <div className="mt-auto pt-2">
            <PriceTag price={product.price} oldPrice={product.oldPrice} size="md" />
          </div>
        </div>
      </Link>

      <div className="px-3.5 pb-3.5 sm:px-4 sm:pb-4">
        <button
          type="button"
          onClick={handleAdd}
          disabled={isOutOfStock}
          aria-label={`${product.name} — ${TEXT.addToCart}`}
          className={[
            'inline-flex h-10 w-full items-center justify-center gap-2 rounded-control text-sm font-semibold transition-colors',
            isOutOfStock
              ? 'cursor-not-allowed bg-ink-100 text-ink-400'
              : inCartQty > 0
                ? 'bg-success-50 text-success-700 ring-1 ring-inset ring-success-500/30 hover:bg-success-100'
                : 'bg-primary-50 text-primary-700 hover:bg-primary-600 hover:text-white',
          ].join(' ')}
        >
          {isOutOfStock ? (
            TEXT.outOfStock
          ) : inCartQty > 0 ? (
            <>
              <Check className="h-4 w-4" aria-hidden="true" />
              კალათაშია ({inCartQty})
            </>
          ) : (
            <>
              <ShoppingCart className="h-4 w-4" aria-hidden="true" />
              {TEXT.addToCart}
            </>
          )}
        </button>
      </div>
    </article>
  );
}

export default memo(ProductCard);
