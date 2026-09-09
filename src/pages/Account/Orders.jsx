import { Link } from 'react-router-dom';
import { Package } from 'lucide-react';
import EmptyState from '../../components/common/EmptyState.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import ProductImage from '../../components/common/ProductImage.jsx';
import { Skeleton } from '../../components/common/Skeleton.jsx';
import Badge from '../../components/common/Badge.jsx';
import { useAsync } from '../../hooks/useProducts.js';
import { useDocumentTitle } from '../../hooks/useDocumentTitle.js';
import * as api from '../../services/api.js';
import { formatDateTime, formatPrice } from '../../utils/format.js';
import { TEXT } from '../../constants/index.js';

const STATUS_LABELS = {
  pending: { label: 'მუშავდება', tone: 'warning' },
  processing: { label: 'მზადდება', tone: 'warning' },
  shipped: { label: 'გზაშია', tone: 'neutral' },
  delivered: { label: 'ჩაბარებულია', tone: 'success' },
};

export default function Orders() {
  useDocumentTitle('ჩემი შეკვეთები');
  const { data: orders, loading, error, reload } = useAsync(() => api.getOrders(), [], {
    initialData: [],
  });

  if (loading) {
    return (
      <div className="space-y-4">
        {[0, 1].map((i) => (
          <Skeleton key={i} className="h-40 w-full" rounded="rounded-card" />
        ))}
      </div>
    );
  }

  if (error) return <ErrorState error={error} onRetry={reload} />;

  if (!orders || orders.length === 0) {
    return (
      <EmptyState
        icon={Package}
        title="შეკვეთები ჯერ არ გაქვთ"
        description="როგორც კი პირველ შეკვეთას გააფორმებთ, ის აქ გამოჩნდება."
        actionLabel={TEXT.backToShop}
        actionTo="/"
      />
    );
  }

  return (
    <ul className="space-y-4">
      {orders.map((order) => {
        const status = STATUS_LABELS[order.status] || STATUS_LABELS.pending;

        return (
          <li key={order.orderNumber} className="rounded-card border border-ink-200 bg-white">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 p-4">
              <div>
                <p className="text-sm font-bold tabular-nums text-ink-900">{order.orderNumber}</p>
                <p className="mt-0.5 text-xs text-ink-500">{formatDateTime(order.createdAt)}</p>
              </div>
              <div className="flex items-center gap-3">
                <Badge tone={status.tone}>{status.label}</Badge>
                <span className="text-base font-bold text-ink-900">
                  {formatPrice(order.totals.total)}
                </span>
              </div>
            </div>

            <ul className="divide-y divide-ink-100 px-4">
              {order.items.map((item) => (
                <li key={item.productId} className="flex items-center gap-3 py-3">
                  <Link to={`/product/${item.snapshot.slug}`} className="shrink-0">
                    <ProductImage
                      src={item.snapshot.image}
                      alt=""
                      className="h-12 w-12 rounded-control border border-ink-200"
                    />
                  </Link>
                  <span className="min-w-0 flex-1">
                    <Link
                      to={`/product/${item.snapshot.slug}`}
                      className="block truncate text-sm font-medium text-ink-900 hover:text-primary-700"
                    >
                      {item.snapshot.name}
                    </Link>
                    <span className="block text-xs text-ink-500">
                      {item.qty} × {formatPrice(item.snapshot.price)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-ink-100 p-4 text-xs text-ink-500">
              <span>
                {order.customer.city}, {order.customer.address}
              </span>
              <Link
                to={`/checkout/success/${order.orderNumber}`}
                className="font-semibold text-primary-700 underline-offset-4 hover:underline"
              >
                დეტალების ნახვა
              </Link>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
