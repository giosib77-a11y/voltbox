import { Truck } from 'lucide-react';
import Button from '../common/Button.jsx';
import { formatPrice } from '../../utils/format.js';
import { t } from '../../i18n/index.js';
import Rich from '../../i18n/Rich.jsx';

/**
 * შეკვეთის შეჯამება. ციფრები გვერდიდან მოდის (utils/pricing.js + `GET /delivery`) —
 * აქ არცერთი არ არის hardcoded.
 *
 * `shipping === null` ნიშნავს „ჯერ უცნობია“: ქალაქი არ არის არჩეული და კალათა
 * ზღვარს ქვემოთაა. მაშინ ჩანს თითო ქალაქის ტარიფი (`cities`) და ჯამი
 * მიწოდების გარეშე — გამოცნობილი ციფრი არა.
 */
export default function CartSummary({
  subtotal = 0,
  shipping = null,
  total = null,
  cities = [],
  remaining = 0,
  freeFrom = null,
  itemsCount = 0,
  savings = 0,
  actionLabel = t('common.checkout'),
  actionTo = '',
  onAction = null,
  actionDisabled = false,
  loading = false,
  children = null,
  className = '',
}) {
  const known = shipping !== null && total !== null;

  return (
    <div className={`rounded-card border border-ink-200 bg-surface p-5 ${className}`}>
      <h2 className="text-base font-bold text-ink-900">{t('cart.summary')}</h2>

      <dl className="mt-4 space-y-2.5 text-sm">
        <div className="flex items-baseline justify-between gap-4">
          <dt className="text-ink-600">
            {t('common.subtotal')}
            {itemsCount > 0 && <span className="text-ink-500"> · {t('cart.units', { count: itemsCount })}</span>}
          </dt>
          <dd className="font-semibold text-ink-900">{formatPrice(subtotal)}</dd>
        </div>

        <div className="flex items-baseline justify-between gap-4">
          <dt className="text-ink-600">{t('common.shipping')}</dt>
          {known ? (
            <dd className={shipping === 0 ? 'font-semibold text-success-700' : 'font-semibold text-ink-900'}>
              {shipping === 0 ? t('common.free') : formatPrice(shipping)}
            </dd>
          ) : (
            <dd className="text-right font-semibold text-ink-900">
              {cities.length > 0
                ? cities.map((city) => `${city.name} ${formatPrice(city.fee)}`).join(' · ')
                : '—'}
            </dd>
          )}
        </div>

        {savings > 0 && (
          <div className="flex items-baseline justify-between gap-4">
            <dt className="text-ink-600">{t('cart.saved')}</dt>
            <dd className="font-semibold text-accent-fg">−{formatPrice(savings)}</dd>
          </div>
        )}

        <div className="border-t border-ink-200 pt-3">
          <div className="flex items-baseline justify-between gap-4">
            <dt className="text-base font-bold text-ink-900">
              {known ? t('common.total') : t('cart.totalWithoutDelivery')}
            </dt>
            <dd className="text-xl font-bold text-ink-900">{formatPrice(known ? total : subtotal)}</dd>
          </div>
        </div>
      </dl>

      {remaining > 0 && subtotal > 0 && (
        <div className="mt-4 flex items-start gap-2.5 rounded-control bg-primary-50 p-3 text-xs leading-relaxed text-primary-800">
          <Truck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>
            <Rich
              k="cart.freeShippingHint"
              values={{ amount: <strong>{formatPrice(remaining)}</strong>, limit: formatPrice(freeFrom) }}
            />
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
        {t('cart.terms', { eta: t('shipping.etaDays') })}
      </p>
    </div>
  );
}
