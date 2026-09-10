/**
 * CustomerDetail: one customer, their addresses and order history.
 *
 * What it does: the profile plus a block/unblock action.
 * Where it fits: /admin/customers/:id.
 * Notes: blocking is confirmed and the dialog says what it does - it also ends
 * every active session, which is not obvious from the word "block".
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Ban, CheckCircle2 } from 'lucide-react';

import Button from '../../components/common/Button.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import Skeleton from '../../components/common/Skeleton.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import { OrderStatusBadge } from '../statuses.jsx';
import { dateOnly, dateTime, money } from '../format.js';
import * as adminApi from '../adminApi.js';

export default function CustomerDetail() {
  const { id } = useParams();
  const [customer, setCustomer] = useState(null);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(() => {
    setError(null);
    adminApi.getCustomer(id).then(setCustomer).catch(setError);
  }, [id]);

  useEffect(load, [load]);

  async function toggleActive() {
    setActionError(null);
    try {
      setCustomer(await adminApi.setCustomerActive(id, !customer.isActive));
    } catch (caught) {
      setActionError(caught);
    } finally {
      setConfirming(false);
    }
  }

  if (error) return <ErrorState title="მომხმარებელი ვერ ჩაიტვირთა" error={error} onRetry={load} />;
  if (!customer) return <Skeleton className="h-96 w-full" />;

  const fullName =
    [customer.firstName, customer.lastName].filter(Boolean).join(' ') || customer.email;

  return (
    <div>
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to="/admin/customers"
            className="mb-1 inline-flex items-center gap-1 text-sm text-ink-600 hover:text-ink-900"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            მომხმარებლები
          </Link>
          <h1 className="text-lg font-semibold text-ink-900">{fullName}</h1>
          <p className="text-sm text-ink-600">
            {customer.email} · რეგისტრაცია {dateOnly(customer.createdAt)}
          </p>
        </div>
        <Button
          variant={customer.isActive ? 'outline' : 'accent'}
          size="sm"
          onClick={() => (customer.isActive ? setConfirming(true) : toggleActive())}
        >
          {customer.isActive ? (
            <Ban className="h-4 w-4" aria-hidden="true" />
          ) : (
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          )}
          {customer.isActive ? 'დაბლოკვა' : 'განბლოკვა'}
        </Button>
      </header>

      {actionError ? (
        <p role="alert" className="mb-4 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
          {actionError.message}
        </p>
      ) : null}

      {!customer.isActive ? (
        <p className="mb-4 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
          ანგარიში დაბლოკილია — შესვლა და API-ით სარგებლობა შეუძლებელია.
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <section className="rounded-xl border border-ink-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-ink-900">შეკვეთები</h2>
          {customer.orders.length ? (
            <ul className="divide-y divide-ink-100 text-sm">
              {customer.orders.map((order) => (
                <li key={order.id} className="flex items-center justify-between gap-2 py-2">
                  <Link
                    to={`/admin/orders/${order.id}`}
                    className="font-medium text-ink-900 hover:text-accent-700"
                  >
                    {order.orderNumber}
                  </Link>
                  <span className="flex items-center gap-2">
                    <span className="hidden text-xs text-ink-500 sm:inline">
                      {dateTime(order.createdAt)}
                    </span>
                    <OrderStatusBadge status={order.status} />
                    <span className="tabular-nums">{money(order.total)}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-600">შეკვეთა ჯერ არ გაუფორმებია.</p>
          )}
        </section>

        <aside className="space-y-4">
          <section className="rounded-xl border border-ink-200 bg-white p-4 text-sm">
            <h2 className="mb-2 text-sm font-semibold text-ink-900">მაჩვენებლები</h2>
            <p className="text-ink-700">
              შეკვეთები: <strong className="tabular-nums">{customer.ordersCount}</strong>
            </p>
            <p className="mt-1 text-ink-700">
              დახარჯული: <strong className="tabular-nums">{money(customer.totalSpent)}</strong>
            </p>
            <p className="mt-1 text-xs text-ink-500">გაუქმებული შეკვეთების გარეშე</p>
            <p className="mt-2 text-ink-700">ტელეფონი: {customer.phone || '—'}</p>
          </section>

          <section className="rounded-xl border border-ink-200 bg-white p-4 text-sm">
            <h2 className="mb-2 text-sm font-semibold text-ink-900">მისამართები</h2>
            {customer.addresses.length ? (
              <ul className="space-y-2">
                {customer.addresses.map((address) => (
                  <li key={address.id}>
                    <span className="block text-ink-900">
                      {address.label || 'მისამართი'}
                      {address.isDefault ? (
                        <span className="ml-1 text-xs text-accent-700">(ძირითადი)</span>
                      ) : null}
                    </span>
                    <span className="text-ink-600">
                      {address.city}, {address.addressLine}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ink-600">შენახული მისამართი არ არის.</p>
            )}
          </section>
        </aside>
      </div>

      <ConfirmDialog
        open={confirming}
        title="ანგარიშის დაბლოკვა"
        description="მომხმარებელი ვეღარ შევა სისტემაში და ყველა მისი აქტიური სესია დაუყოვნებლივ დასრულდება. შეკვეთების ისტორია ხელუხლებელი რჩება. განბლოკვა ნებისმიერ დროს შეიძლება."
        confirmLabel="დაბლოკვა"
        onConfirm={toggleActive}
        onClose={() => setConfirming(false)}
      />
    </div>
  );
}
