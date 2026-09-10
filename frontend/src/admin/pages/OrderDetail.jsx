/**
 * OrderDetail: one order, its items and its timeline.
 *
 * What it does: shows the snapshotted order and offers exactly the status moves
 * the server reports as allowed.
 * Where it fits: /admin/orders/:id.
 * Notes: the buttons come from `allowedTransitions` in the response. The UI does
 * not know the state machine and must not - a second copy of the graph is how
 * the two drift apart.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import Button from '../../components/common/Button.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import Skeleton from '../../components/common/Skeleton.jsx';
import ProductImage from '../../components/common/ProductImage.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import { ORDER_STATUSES, OrderStatusBadge } from '../statuses.jsx';
import { dateTime, money } from '../format.js';
import * as adminApi from '../adminApi.js';

export default function OrderDetail() {
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [pendingStatus, setPendingStatus] = useState(null);

  const load = useCallback(() => {
    setError(null);
    adminApi.getOrder(id).then(setOrder).catch(setError);
  }, [id]);

  useEffect(load, [load]);

  async function applyStatus(to) {
    setActionError(null);
    try {
      setOrder(await adminApi.changeOrderStatus(id, to));
    } catch (caught) {
      setActionError(caught);
    } finally {
      setPendingStatus(null);
    }
  }

  if (error) return <ErrorState title="შეკვეთა ვერ ჩაიტვირთა" error={error} onRetry={load} />;
  if (!order) return <Skeleton className="h-96 w-full" />;

  const customer = order.customer || {};

  return (
    <div>
      <header className="mb-4">
        <Link
          to="/admin/orders"
          className="mb-1 inline-flex items-center gap-1 text-sm text-ink-600 hover:text-ink-900"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          შეკვეთები
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-lg font-semibold text-ink-900">{order.orderNumber}</h1>
          <OrderStatusBadge status={order.status} />
          <span className="text-sm text-ink-600">{dateTime(order.createdAt)}</span>
        </div>
      </header>

      {actionError ? (
        <p role="alert" className="mb-4 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
          {actionError.message}
        </p>
      ) : null}

      {order.allowedTransitions.length ? (
        <div className="mb-4 flex flex-wrap gap-2">
          {order.allowedTransitions.map((next) => (
            <Button
              key={next}
              size="sm"
              variant={next === 'cancelled' ? 'outline' : 'accent'}
              onClick={() => setPendingStatus(next)}
            >
              {ORDER_STATUSES[next]?.label || next}
            </Button>
          ))}
        </div>
      ) : (
        <p className="mb-4 text-sm text-ink-600">
          ეს შეკვეთა დასრულებულია — სტატუსი აღარ იცვლება.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-4">
          <section className="rounded-xl border border-ink-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">პოზიციები</h2>
            <ul className="divide-y divide-ink-100">
              {order.items.map((item) => (
                <li key={item.id} className="flex items-center gap-3 py-2">
                  <ProductImage
                    src={item.imageUrl}
                    alt=""
                    className="h-10 w-10 shrink-0 rounded object-cover"
                  />
                  <div className="min-w-0 flex-1">
                    {/* The snapshot, not the live product: the order must read
                        as it did when it was placed. */}
                    <span className="block truncate text-ink-900">{item.productName}</span>
                    <span className="text-xs text-ink-500">
                      {money(item.unitPrice)} × {item.quantity}
                    </span>
                  </div>
                  <span className="tabular-nums text-ink-900">{money(item.lineTotal)}</span>
                </li>
              ))}
            </ul>

            <dl className="mt-3 space-y-1 border-t border-ink-200 pt-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-600">ჯამი</dt>
                <dd className="tabular-nums">{money(order.subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-600">მიწოდება</dt>
                <dd className="tabular-nums">{money(order.shipping)}</dd>
              </div>
              <div className="flex justify-between font-semibold text-ink-900">
                <dt>სულ</dt>
                <dd className="tabular-nums">{money(order.total)}</dd>
              </div>
            </dl>
          </section>

          <section className="rounded-xl border border-ink-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">სტატუსის ისტორია</h2>
            <ol className="space-y-2 text-sm">
              {order.history.map((entry, index) => (
                <li key={index} className="flex flex-wrap items-baseline gap-2">
                  <span className="text-ink-500">{dateTime(entry.createdAt)}</span>
                  <span className="text-ink-900">
                    {ORDER_STATUSES[entry.fromStatus]?.label || entry.fromStatus} →{' '}
                    {ORDER_STATUSES[entry.toStatus]?.label || entry.toStatus}
                  </span>
                  {entry.note ? <span className="text-ink-600">— {entry.note}</span> : null}
                </li>
              ))}
            </ol>
          </section>
        </div>

        <aside className="space-y-4">
          <section className="rounded-xl border border-ink-200 bg-white p-4 text-sm">
            <h2 className="mb-2 text-sm font-semibold text-ink-900">მყიდველი</h2>
            <p className="text-ink-900">{order.customerName}</p>
            <p className="text-ink-600">{order.phone || '—'}</p>
            <p className="text-ink-600">{order.email || '—'}</p>
            <p className="mt-2 text-ink-700">
              {order.city || '—'}
              {customer.address ? `, ${customer.address}` : ''}
            </p>
            {order.notes ? (
              <p className="mt-2 rounded bg-ink-50 p-2 text-ink-700">{order.notes}</p>
            ) : null}
          </section>

          <section className="rounded-xl border border-ink-200 bg-white p-4 text-sm">
            <h2 className="mb-2 text-sm font-semibold text-ink-900">გადახდა</h2>
            <p className="text-ink-700">
              {order.paymentMethod === 'cash' ? 'ნაღდი მიწოდებისას' : order.paymentMethod}
            </p>
          </section>
        </aside>
      </div>

      <ConfirmDialog
        open={Boolean(pendingStatus)}
        title={`სტატუსი: ${ORDER_STATUSES[pendingStatus]?.label || pendingStatus || ''}`}
        description={
          pendingStatus === 'cancelled'
            ? 'შეკვეთა გაუქმდება და პროდუქტები მარაგში დაბრუნდება. ეს ქმედება შეუქცევადია.'
            : 'შეკვეთის სტატუსი შეიცვლება.'
        }
        confirmLabel="დადასტურება"
        variant={pendingStatus === 'cancelled' ? 'danger' : 'accent'}
        onConfirm={() => applyStatus(pendingStatus)}
        onClose={() => setPendingStatus(null)}
      />
    </div>
  );
}
