import { Link } from 'react-router';
import { Trash2 } from 'lucide-react';
import ProductImage from '../common/ProductImage.jsx';
import QuantityStepper from './QuantityStepper.jsx';
import { formatPrice } from '../../utils/format.js';
import { MAX_LINE_QTY } from '../../constants/index.js';
import { t } from '../../i18n/index.js';

/**
 * კალათის ერთი ჩანაწერი.
 * მონაცემები მოდის `snapshot`-იდან — ისე, როგორც მომხმარებელმა დაინახა.
 */
export default function CartItem({ item, onQtyChange, onRemove }) {
  const { snapshot, qty, productId } = item;
  const lineTotal = snapshot.price * qty;
  const maxQty = snapshot.stock > 0 ? Math.min(snapshot.stock, MAX_LINE_QTY) : 1;

  return (
    <li className="flex gap-3 py-5 sm:gap-4">
      <Link to={`/product/${snapshot.slug}`} className="shrink-0" aria-label={snapshot.name}>
        <ProductImage
          src={snapshot.image}
          alt={snapshot.name}
          shopPlaceholder
          className="h-[72px] w-[72px] border border-line sm:h-[88px] sm:w-[88px]"
        />
      </Link>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link
              to={`/product/${snapshot.slug}`}
              className="line-clamp-2-fallback font-serif text-[15px] font-normal leading-snug text-fg hover:text-primary-700 sm:text-base"
            >
              {snapshot.name}
            </Link>
            <p className="mt-1 text-xs text-ink-500">
              {t('cart.perUnit', { price: formatPrice(snapshot.price) })}
              {snapshot.stock > 0 && snapshot.stock <= 3 && (
                <span className="ml-2 font-medium text-warning-600">
                  {t('cart.stockLeft', { count: snapshot.stock })}
                </span>
              )}
            </p>
          </div>

          <button
            type="button"
            onClick={() => onRemove(productId)}
            aria-label={t('cart.removeItem', { name: snapshot.name })}
            className="-mr-1.5 -mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-control text-ink-600 transition-colors hover:bg-danger-50 hover:text-danger-fg"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="mt-auto flex flex-wrap items-center justify-between gap-3">
          <QuantityStepper
            size="sm"
            value={qty}
            min={1}
            max={maxQty}
            onChange={(next) => onQtyChange(productId, next)}
            label={t('cart.itemQuantity', { name: snapshot.name })}
          />
          <span className="font-display text-xl font-medium lining-nums text-ink-900">{formatPrice(lineTotal)}</span>
        </div>
        {qty >= MAX_LINE_QTY && (
          <p className="text-xs text-ink-500">{t('cart.maxPerProduct', { count: MAX_LINE_QTY })}</p>
        )}
      </div>
    </li>
  );
}
