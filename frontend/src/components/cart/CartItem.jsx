import { Link } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import ProductImage from '../common/ProductImage.jsx';
import QuantityStepper from './QuantityStepper.jsx';
import { formatPrice } from '../../utils/format.js';
import { TEXT } from '../../constants/index.js';

/**
 * კალათის ერთი ჩანაწერი.
 * მონაცემები მოდის `snapshot`-იდან — ისე, როგორც მომხმარებელმა დაინახა.
 */
export default function CartItem({ item, onQtyChange, onRemove }) {
  const { snapshot, qty, productId } = item;
  const lineTotal = snapshot.price * qty;
  const maxQty = snapshot.stock > 0 ? snapshot.stock : 1;

  return (
    <li className="flex gap-3 py-4 sm:gap-4">
      <Link to={`/product/${snapshot.slug}`} className="shrink-0" aria-label={snapshot.name}>
        <ProductImage
          src={snapshot.image}
          alt={snapshot.name}
          className="h-20 w-20 rounded-control border border-ink-200 sm:h-24 sm:w-24"
        />
      </Link>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link
              to={`/product/${snapshot.slug}`}
              className="line-clamp-2-fallback text-sm font-semibold leading-snug text-ink-900 hover:text-primary-700 sm:text-base"
            >
              {snapshot.name}
            </Link>
            <p className="mt-1 text-xs text-ink-500">
              {formatPrice(snapshot.price)} / ცალი
              {snapshot.stock > 0 && snapshot.stock <= 3 && (
                <span className="ml-2 font-medium text-warning-600">
                  მარაგშია {snapshot.stock}
                </span>
              )}
            </p>
          </div>

          <button
            type="button"
            onClick={() => onRemove(productId)}
            aria-label={`${snapshot.name} — ${TEXT.remove}`}
            className="-mr-1.5 -mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-danger-50 hover:text-danger-600"
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
            label={`${snapshot.name} — ${TEXT.quantity}`}
          />
          <span className="text-base font-bold text-ink-900">{formatPrice(lineTotal)}</span>
        </div>
      </div>
    </li>
  );
}
