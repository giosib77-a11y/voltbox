import { Truck } from 'lucide-react';
import Button from '../common/Button.jsx';
import { formatPrice } from '../../utils/format.js';
import { amountToFreeShipping } from '../../utils/pricing.js';
import { SHIPPING, TEXT } from '../../constants/index.js';

/**
 * შეკვეთის შეჯამება. მიწოდების ლოგიკა მოდის `utils/pricing.js`-იდან —
 * აქ არცერთი ციფრი არ არის hardcoded.
 */
export default function CartSummary({
  subtotal = 0,
  shipping = 0,
  total = 0,
  itemsCount = 0,
  savings = 0,
  actionLabel = TEXT.checkout,
  actionTo = '',
  onAction = null,
  actionDisabled = false,
  loading = false,
  children = null,
  className = '',
}) {
  const remaining = amountToFreeShipping(subtotal);

  return (
    <div className={`rounded-card border border-ink-200 bg-white p-5 ${className}`}>
      <h2 className="text-base font-bold text-ink-900">შეკვეთის შეჯამება</h2>

      <dl className="mt-4 space-y-2.5 text-sm">
        <div className="flex items-baseline justify-between gap-4">
          <dt className="text-ink-600">
            {TEXT.subtotal}
            {itemsCount > 0 && <span className="text-ink-500"> · {itemsCount} ცალი</span>}
          </dt>
          <dd className="font-semibold text-ink-900">{formatPrice(subtotal)}</dd>
        </div>

        <div className="flex items-baseline justify-between gap-4">
          <dt className="text-ink-600">{TEXT.shipping}</dt>
          <dd className={shipping === 0 ? 'font-semibold text-success-600' : 'font-semibold text-ink-900'}>
            {shipping === 0 ? TEXT.free : formatPrice(shipping)}
          </dd>
        </div>

        {savings > 0 && (
          <div className="flex items-baseline justify-between gap-4">
            <dt className="text-ink-600">დაზოგილი</dt>
            <dd className="font-semibold text-accent-600">−{formatPrice(savings)}</dd>
          </div>
        )}

        <div className="border-t border-ink-200 pt-3">
          <div className="flex items-baseline justify-between gap-4">
            <dt className="text-base font-bold text-ink-900">{TEXT.total}</dt>
            <dd className="text-xl font-bold text-ink-900">{formatPrice(total)}</dd>
          </div>
        </div>
      </dl>

      {remaining > 0 && subtotal > 0 && (
        <div className="mt-4 flex items-start gap-2.5 rounded-control bg-primary-50 p-3 text-xs leading-relaxed text-primary-800">
          <Truck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>
            დაამატე კიდევ <strong>{formatPrice(remaining)}</strong> და მიწოდება უფასო იქნება
            (ზღვარი — {formatPrice(SHIPPING.freeThreshold)}).
          </p>
        </div>
      )}

      {(actionTo || onAction) && (
        <Button
          className="mt-5"
          size="lg"
          fullWidth
          to={actionTo || undefined}
          onClick={onAction || undefined}
          disabled={actionDisabled}
          loading={loading}
        >
          {actionLabel}
        </Button>
      )}

      {children}

      <p className="mt-4 text-center text-xs text-ink-500">
        მიწოდება {SHIPPING.etaDays} · დაბრუნება 14 დღეში
      </p>
    </div>
  );
}
