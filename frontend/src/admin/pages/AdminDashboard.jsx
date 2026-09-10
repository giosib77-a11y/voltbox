/**
 * AdminDashboard: the /admin landing page.
 *
 * What it does: KPI figures, orders per status, low stock and recent activity -
 * all from one request.
 * Where it fits: the index route of the admin tree.
 * Notes: every number comes from GET /admin/dashboard, which computes them with
 * SQL aggregates. Nothing is summed in the browser, so these figures cannot
 * disagree with what the orders list shows.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import ErrorState from '../../components/common/ErrorState.jsx';
import Skeleton from '../../components/common/Skeleton.jsx';
import { OrderStatusBadge } from '../statuses.jsx';
import { money } from '../format.js';
import * as adminApi from '../adminApi.js';

function Kpi({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-ink-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-ink-500">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-ink-900">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-ink-500">{hint}</p> : null}
    </div>
  );
}

/** A titled panel with an optional link to the full view. */
function Panel({ title, to, linkLabel, children }) {
  return (
    <section className="rounded-xl border border-ink-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink-900">{title}</h2>
        {to ? (
          <Link to={to} className="text-sm text-accent-700 hover:underline">
            {linkLabel}
          </Link>
        ) : null}
      </div>
      {children}
    </section>
  );
}

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    adminApi.getDashboard().then(setData).catch(setError);
  }, []);

  useEffect(load, [load]);

  if (error) return <ErrorState title="მაჩვენებლები ვერ ჩაიტვირთა" error={error} onRetry={load} />;
  if (!data) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-ink-900">მიმოხილვა</h1>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="დღევანდელი გაყიდვები"
          value={money(data.salesToday)}
          hint="გაუქმებულის გარეშე"
        />
        <Kpi label="დღევანდელი შეკვეთები" value={data.ordersToday} />
        <Kpi label="სულ გაყიდვები" value={money(data.salesTotal)} />
        <Kpi
          label="აქტიური პროდუქტები"
          value={data.activeProducts}
          hint={data.lowStockCount ? `${data.lowStockCount} იწურება` : 'მარაგი წესრიგშია'}
        />
      </div>

      <Panel title="შეკვეთები სტატუსებით">
        <ul className="flex flex-wrap gap-2">
          {Object.entries(data.ordersByStatus).map(([status, count]) => (
            <li key={status}>
              <Link
                to={`/admin/orders?status=${status}`}
                className="flex items-center gap-2 rounded-lg border border-ink-200 px-3 py-1.5 text-sm hover:bg-ink-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700"
              >
                <OrderStatusBadge status={status} />
                <span className="tabular-nums font-medium text-ink-900">{count}</span>
              </Link>
            </li>
          ))}
        </ul>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="ბოლო შეკვეთები" to="/admin/orders" linkLabel="ყველა">
          {data.latestOrders.length ? (
            <ul className="divide-y divide-ink-100 text-sm">
              {data.latestOrders.map((order) => (
                <li key={order.id} className="flex items-center justify-between gap-2 py-2">
                  <Link
                    to={`/admin/orders/${order.id}`}
                    className="font-medium text-ink-900 hover:text-accent-700"
                  >
                    {order.orderNumber}
                  </Link>
                  <span className="flex items-center gap-2">
                    <OrderStatusBadge status={order.status} />
                    <span className="tabular-nums">{money(order.total)}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-600">შეკვეთა ჯერ არ არის.</p>
          )}
        </Panel>

        <Panel title="მარაგი იწურება" to="/admin/inventory?only=low" linkLabel="მარაგი">
          {data.lowStock.length ? (
            <ul className="divide-y divide-ink-100 text-sm">
              {data.lowStock.map((product) => (
                <li key={product.id} className="flex items-center justify-between gap-2 py-2">
                  <span className="truncate text-ink-900">{product.name}</span>
                  <span className="tabular-nums text-danger-700">
                    {product.stock} / {product.threshold}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-600">ყველა პროდუქტს საკმარისი მარაგი აქვს.</p>
          )}
        </Panel>

        <Panel title="ტოპ პროდუქტები (30 დღე)">
          {data.topProducts.length ? (
            <ul className="divide-y divide-ink-100 text-sm">
              {data.topProducts.map((product) => (
                <li
                  key={product.productId}
                  className="flex items-center justify-between gap-2 py-2"
                >
                  <span className="truncate text-ink-900">{product.name}</span>
                  <span className="whitespace-nowrap text-ink-600">
                    <span className="tabular-nums font-medium text-ink-900">
                      {product.quantity}
                    </span>{' '}
                    ცალი · {money(product.revenue)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-600">ბოლო 30 დღეში გაყიდვა არ ყოფილა.</p>
          )}
        </Panel>

        <Panel title="ბოლოს დამატებული" to="/admin/products" linkLabel="პროდუქტები">
          {data.latestProducts.length ? (
            <ul className="divide-y divide-ink-100 text-sm">
              {data.latestProducts.map((product) => (
                <li key={product.id} className="flex items-center justify-between gap-2 py-2">
                  <Link
                    to={`/admin/products/${product.id}`}
                    className="truncate text-ink-900 hover:text-accent-700"
                  >
                    {product.name}
                  </Link>
                  <span className="tabular-nums text-ink-600">{money(product.price)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-600">პროდუქტი ჯერ არ არის.</p>
          )}
        </Panel>
      </div>
    </div>
  );
}
