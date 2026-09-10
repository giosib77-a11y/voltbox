import { useParams } from 'react-router-dom';
import { CheckCircle2, Copy, Package, Phone, Truck } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import EmptyState from '../components/common/EmptyState.jsx';
import ErrorState from '../components/common/ErrorState.jsx';
import ProductImage from '../components/common/ProductImage.jsx';
import { Skeleton } from '../components/common/Skeleton.jsx';
import { useAsync } from '../hooks/useProducts.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { useToast } from '../hooks/useToast.js';
import * as api from '../services/api.js';
import { formatDateTime, formatPrice } from '../utils/format.js';
import { PAYMENT_METHODS, SHIPPING, TEXT } from '../constants/index.js';

/** შეკვეთის დადასტურების გვერდი — ნომრით და სრული დეტალებით. */
export default function CheckoutSuccess() {
  const { id: orderNumber } = useParams();
  const toast = useToast();
  useDocumentTitle(`შეკვეთა ${orderNumber || ''}`);

  const { data: order, loading, error, reload } = useAsync(
    () => api.getOrderByNumber(orderNumber),
    [orderNumber],
  );

  if (loading) {
    return (
      <div className="container-page max-w-3xl py-10">
        <Skeleton className="mx-auto h-16 w-16" rounded="rounded-full" />
        <Skeleton className="mx-auto mt-5 h-8 w-72" />
        <Skeleton className="mt-8 h-64 w-full" rounded="rounded-card" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-page max-w-3xl py-14">
        {error.status === 404 ? (
          <EmptyState
            title="შეკვეთა ვერ მოიძებნა"
            description="შესაძლოა ბმული არასწორია ან შეკვეთა სხვა მოწყობილობაზე გაფორმდა."
            actionLabel={TEXT.backToShop}
            actionTo="/"
          />
        ) : (
          <ErrorState error={error} onRetry={reload} />
        )}
      </div>
    );
  }

  if (!order) return null;

  const paymentLabel =
    PAYMENT_METHODS.find((method) => method.value === order.paymentMethod)?.label || '—';

  function copyOrderNumber() {
    navigator.clipboard
      ?.writeText(order.orderNumber)
      .then(() => toast.success('შეკვეთის ნომერი დაკოპირდა'))
      .catch(() => toast.error('კოპირება ვერ მოხერხდა'));
  }

  return (
    <div className="container-page max-w-3xl py-8 lg:py-12">
      <div className="text-center">
        <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-success-50">
          <CheckCircle2 className="h-9 w-9 text-success-600" aria-hidden="true" />
        </span>
        <h1 className="mt-5 text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
          შეკვეთა მიღებულია!
        </h1>
        <p className="mx-auto mt-2.5 max-w-md text-sm leading-relaxed text-ink-600">
          გმადლობთ შეკვეთისთვის. ოპერატორი დაგიკავშირდებათ მითითებულ ნომერზე დეტალების დასაზუსტებლად.
        </p>

        <div className="mt-5 inline-flex items-center gap-2 rounded-card border border-ink-200 bg-white px-4 py-2.5">
          <span className="text-sm text-ink-500">შეკვეთის ნომერი:</span>
          <strong className="text-base tabular-nums text-ink-900">{order.orderNumber}</strong>
          <button
            type="button"
            onClick={copyOrderNumber}
            aria-label="შეკვეთის ნომრის კოპირება"
            className="ml-1 flex h-8 w-8 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-800"
          >
            <Copy className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <section className="mt-8 rounded-card border border-ink-200 bg-white p-5 sm:p-6">
        <h2 className="text-base font-bold text-ink-900">შეკვეთის დეტალები</h2>

        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-ink-500">თარიღი</dt>
            <dd className="mt-0.5 font-medium text-ink-900">{formatDateTime(order.createdAt)}</dd>
          </div>
          <div>
            <dt className="text-ink-500">გადახდა</dt>
            <dd className="mt-0.5 font-medium text-ink-900">{paymentLabel}</dd>
          </div>
          <div>
            <dt className="text-ink-500">მიმღები</dt>
            <dd className="mt-0.5 font-medium text-ink-900">
              {order.customer.firstName} {order.customer.lastName}
            </dd>
          </div>
          <div>
            <dt className="text-ink-500">ტელეფონი</dt>
            <dd className="mt-0.5 flex items-center gap-1.5 font-medium text-ink-900">
              <Phone className="h-3.5 w-3.5 text-ink-400" aria-hidden="true" />
              {order.customer.phone}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-ink-500">მისამართი</dt>
            <dd className="mt-0.5 font-medium text-ink-900">
              {order.customer.city}, {order.customer.address}
            </dd>
          </div>
          {order.customer.comment && (
            <div className="sm:col-span-2">
              <dt className="text-ink-500">კომენტარი</dt>
              <dd className="mt-0.5 text-ink-700">{order.customer.comment}</dd>
            </div>
          )}
        </dl>

        <ul className="mt-6 divide-y divide-ink-100 border-t border-ink-200 pt-2">
          {order.items.map((item) => (
            <li key={item.productId} className="flex items-center gap-3 py-3">
              <ProductImage
                src={item.snapshot.image}
                alt=""
                className="h-14 w-14 shrink-0 rounded-control border border-ink-200"
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-ink-900">
                  {item.snapshot.name}
                </span>
                <span className="block text-xs text-ink-500">
                  {item.qty} × {formatPrice(item.snapshot.price)}
                </span>
              </span>
              <span className="shrink-0 text-sm font-semibold text-ink-900">
                {formatPrice(item.snapshot.price * item.qty)}
              </span>
            </li>
          ))}
        </ul>

        <dl className="mt-4 space-y-2 border-t border-ink-200 pt-4 text-sm">
          <div className="flex justify-between">
            <dt className="text-ink-600">{TEXT.subtotal}</dt>
            <dd className="font-medium text-ink-900">{formatPrice(order.totals.subtotal)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-ink-600">{TEXT.shipping}</dt>
            <dd className="font-medium text-ink-900">
              {order.totals.shipping === 0 ? TEXT.free : formatPrice(order.totals.shipping)}
            </dd>
          </div>
          <div className="flex justify-between border-t border-ink-100 pt-2">
            <dt className="text-base font-bold text-ink-900">{TEXT.total}</dt>
            <dd className="text-lg font-bold text-ink-900">{formatPrice(order.totals.total)}</dd>
          </div>
        </dl>

        <p className="mt-5 flex items-center gap-2 rounded-control bg-primary-50 px-3.5 py-3 text-xs text-primary-900">
          <Truck className="h-4 w-4 shrink-0" aria-hidden="true" />
          სავარაუდო მიწოდება — {SHIPPING.etaDays}.
        </p>
      </section>

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Button to="/">{TEXT.continueShopping}</Button>
        <Button variant="outline" to="/account/orders">
          <Package className="h-4 w-4" aria-hidden="true" />
          ჩემი შეკვეთები
        </Button>
      </div>
    </div>
  );
}
