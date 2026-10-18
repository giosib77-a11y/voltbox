/**
 * OrderList: the admin's order table.
 *
 * What it does: search, status and date filters, pagination.
 * Where it fits: /admin/orders.
 * Notes: filters live in the URL, like every other admin list. Phone search is
 * normalised on the server, so an admin can type the number in whatever shape
 * they are looking at.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Search } from 'lucide-react';

import Button from '../../components/common/Button.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import EmptyState from '../../components/common/EmptyState.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import Select from '../../components/common/Select.jsx';
import Input from '../../components/common/Input.jsx';
import DataTable from '../components/DataTable.jsx';
import AdminPagination from '../components/AdminPagination.jsx';
import { ORDER_STATUSES, OrderStatusBadge } from '../statuses.jsx';
import { dateTime, money } from '../format.js';
import * as adminApi from '../adminApi.js';
import { useDebounce } from '../../hooks/useDebounce.js';

const LIMIT = 20;

export default function OrderList() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get('page') || 1);
  const status = params.get('status') || '';
  const dateFrom = params.get('dateFrom') || '';
  const dateTo = params.get('dateTo') || '';
  const search = params.get('q') || '';
  const trash = params.get('trash') === 'true';

  const [query, setQuery] = useState(search);
  const debouncedQuery = useDebounce(query, 300);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [restoring, setRestoring] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteError, setDeleteError] = useState(null);
  const [reloadToken, setReloadToken] = useState(0);

  const setParam = useCallback(
    (key, value) => {
      const next = new URLSearchParams(params);
      if (!value) next.delete(key);
      else next.set(key, String(value));
      if (key !== 'page') next.delete('page');
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  useEffect(() => {
    if (search !== debouncedQuery) setParam('q', debouncedQuery);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    adminApi
      .listOrders({
        page,
        limit: LIMIT,
        q: search || undefined,
        status: status || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        trash: trash || undefined,
      })
      .then((result) => !cancelled && setData(result))
      .catch((caught) => !cancelled && setError(caught))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [page, search, status, dateFrom, dateTo, trash, reloadToken]);

  async function handleRestore(order) {
    setActionError(null);
    setRestoring(order.id);
    try {
      await adminApi.restoreOrder(order.id);
      setReloadToken((token) => token + 1);
    } catch (caught) {
      setActionError(caught);
    } finally {
      setRestoring(null);
    }
  }

  async function handleDeleteForever() {
    setDeleteError(null);
    try {
      await adminApi.deleteOrderForever(deleting.id);
      setDeleting(null);
      setReloadToken((token) => token + 1);
    } catch (caught) {
      setDeleteError(caught);
    }
  }

  const baseColumns = [
    {
      key: 'number',
      header: 'შეკვეთა',
      render: (order) => (
        <Link
          to={`/admin/orders/${order.id}`}
          className="font-medium text-ink-900 hover:text-accent-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700"
        >
          {order.orderNumber}
        </Link>
      ),
    },
    {
      key: 'customer',
      header: 'მყიდველი',
      render: (order) => (
        <span>
          <span className="block text-ink-900">{order.customerName}</span>
          <span className="text-xs text-ink-500">{order.phone || order.email || '—'}</span>
        </span>
      ),
    },
    {
      key: 'city',
      header: 'ქალაქი',
      render: (order) => <span className="text-ink-700">{order.city || '—'}</span>,
    },
    {
      key: 'items',
      header: 'პოზიცია',
      align: 'right',
      render: (order) => <span className="tabular-nums">{order.itemCount}</span>,
    },
    {
      key: 'total',
      header: 'ჯამი',
      align: 'right',
      render: (order) => <span className="tabular-nums">{money(order.total)}</span>,
    },
    {
      key: 'status',
      header: 'სტატუსი',
      render: (order) => <OrderStatusBadge status={order.status} />,
    },
    {
      key: 'created',
      header: 'თარიღი',
      render: (order) => (
        <span className="whitespace-nowrap text-ink-600">{dateTime(order.createdAt)}</span>
      ),
    },
  ];

  const trashColumns = [
    {
      key: 'deleted',
      header: 'წაშლილია',
      render: (order) => (
        <span className="whitespace-nowrap text-ink-600">{dateTime(order.deletedAt)}</span>
      ),
    },
    {
      key: 'daysLeft',
      header: 'დარჩა',
      align: 'right',
      render: (order) => <span className="tabular-nums">{daysLeft(order.purgeAt)} დღე</span>,
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (order) => (
        <span className="flex justify-end gap-1">
          <Button
            variant="outline"
            size="xs"
            onClick={() => handleRestore(order)}
            loading={restoring === order.id}
            aria-label={`${order.orderNumber} — აღდგენა`}
          >
            აღდგენა
          </Button>
          <Button
            variant="danger"
            size="xs"
            onClick={() => {
              setDeleteError(null);
              setDeleting(order);
            }}
            aria-label={`${order.orderNumber} — სამუდამოდ წაშლა`}
          >
            სამუდამოდ წაშლა
          </Button>
        </span>
      ),
    },
  ];

  const columns = trash ? [...baseColumns, ...trashColumns] : baseColumns;

  return (
    <div>
      <header className="mb-4">
        <h1 className="text-lg font-semibold text-ink-900">შეკვეთები</h1>
        <p className="text-sm text-ink-600">{data ? `${data.total} შეკვეთა` : 'იტვირთება…'}</p>
      </header>

      <div className="mb-3 grid gap-2 rounded-xl border border-ink-200 bg-white p-3 lg:grid-cols-[1fr_auto_auto_auto]">
        <label className="relative">
          <span className="sr-only">ძებნა ნომრით, სახელით, ტელეფონით ან ელფოსტით</span>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="ნომერი, სახელი, ტელეფონი, ელფოსტა"
            className="h-9 w-full rounded-lg border border-ink-300 pl-9 pr-3 text-sm focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/30"
          />
        </label>
        <Select
          aria-label="სტატუსი"
          value={status}
          placeholder="ყველა სტატუსი"
          options={Object.entries(ORDER_STATUSES).map(([value, tone]) => ({
            value,
            label: tone.label,
          }))}
          onChange={(event) => setParam('status', event.target.value)}
        />
        <Input
          aria-label="თარიღიდან"
          type="date"
          value={dateFrom}
          onChange={(event) => setParam('dateFrom', event.target.value)}
        />
        <Input
          aria-label="თარიღამდე"
          type="date"
          value={dateTo}
          onChange={(event) => setParam('dateTo', event.target.value)}
        />
      </div>

      <label className="mb-3 flex w-fit items-center gap-2 text-sm text-ink-700">
        <input
          type="checkbox"
          checked={trash}
          onChange={(event) => setParam('trash', event.target.checked)}
          className="h-4 w-4 rounded border-ink-300 text-accent-600 focus:ring-accent-600/30"
        />
        სანაგვე
      </label>

      {actionError ? (
        <p role="alert" className="mb-3 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
          {actionError.message}
        </p>
      ) : null}

      {error ? (
        <ErrorState title="შეკვეთები ვერ ჩაიტვირთა" error={error} />
      ) : (
        <>
          <DataTable
            caption={trash ? 'სანაგვეში მყოფი შეკვეთები' : 'შეკვეთების სია'}
            columns={columns}
            rows={data?.items || []}
            loading={loading}
            empty={
              trash ? (
                <EmptyState title="სანაგვე ცარიელია" />
              ) : (
                <EmptyState
                  title="შეკვეთა ვერ მოიძებნა"
                  description="შეცვალეთ ფილტრები ან თარიღების შუალედი."
                />
              )
            }
          />
          {data ? (
            <AdminPagination
              page={data.page}
              totalPages={data.totalPages}
              total={data.total}
              limit={data.limit}
              onPage={(next) => setParam('page', next)}
            />
          ) : null}
        </>
      )}

      <ConfirmDialog
        open={Boolean(deleting)}
        title="შეკვეთის სამუდამოდ წაშლა"
        description={
          deleteError
            ? deleteError.message
            : `${deleting?.orderNumber} სამუდამოდ წაიშლება და მისი აღდგენა შეუძლებელი იქნება. ქმედება შეუქცევადია.`
        }
        confirmLabel="სამუდამოდ წაშლა"
        variant="danger"
        onConfirm={handleDeleteForever}
        onClose={() => {
          setDeleting(null);
          setDeleteError(null);
        }}
      />
    </div>
  );
}

/** Whole days until the purge, rounded up and never below 0. */
function daysLeft(purgeAt) {
  const ms = new Date(purgeAt).getTime() - Date.now();
  return Number.isFinite(ms) ? Math.max(0, Math.ceil(ms / 86_400_000)) : 0;
}
