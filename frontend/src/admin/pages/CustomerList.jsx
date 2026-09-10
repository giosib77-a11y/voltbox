/**
 * CustomerList: registered customers with their order aggregates.
 *
 * What it does: search, an active/blocked filter, pagination.
 * Where it fits: /admin/customers.
 * Notes: orders count and total spent come from the server as subqueries, so
 * this page stays one request no matter how much history a shop has - and the
 * figures match the dashboard by construction.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Search } from 'lucide-react';

import Button from '../../components/common/Button.jsx';
import Select from '../../components/common/Select.jsx';
import EmptyState from '../../components/common/EmptyState.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import DataTable from '../components/DataTable.jsx';
import AdminPagination from '../components/AdminPagination.jsx';
import { dateOnly, money } from '../format.js';
import * as adminApi from '../adminApi.js';

const LIMIT = 20;

export default function CustomerList() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get('page') || 1);
  const state = params.get('state') || '';
  const search = params.get('q') || '';

  const [query, setQuery] = useState(search);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
    let cancelled = false;
    setLoading(true);
    setError(null);
    adminApi
      .listCustomers({
        page,
        limit: LIMIT,
        q: search || undefined,
        isActive: state === 'active' ? true : state === 'blocked' ? false : undefined,
      })
      .then((result) => !cancelled && setData(result))
      .catch((caught) => !cancelled && setError(caught))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [page, search, state]);

  const columns = [
    {
      key: 'name',
      header: 'მომხმარებელი',
      render: (customer) => (
        <Link
          to={`/admin/customers/${customer.id}`}
          className="focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700"
        >
          <span className="block font-medium text-ink-900">
            {[customer.firstName, customer.lastName].filter(Boolean).join(' ') || '—'}
          </span>
          <span className="text-xs text-ink-500">{customer.email}</span>
        </Link>
      ),
    },
    {
      key: 'phone',
      header: 'ტელეფონი',
      render: (customer) => <span className="text-ink-700">{customer.phone || '—'}</span>,
    },
    {
      key: 'orders',
      header: 'შეკვეთები',
      align: 'right',
      render: (customer) => <span className="tabular-nums">{customer.ordersCount}</span>,
    },
    {
      key: 'spent',
      header: 'დახარჯული',
      align: 'right',
      render: (customer) => (
        <span className="tabular-nums">{money(customer.totalSpent)}</span>
      ),
    },
    {
      key: 'status',
      header: 'სტატუსი',
      render: (customer) => (
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
            customer.isActive ? 'bg-success-50 text-success-700' : 'bg-danger-50 text-danger-700'
          }`}
        >
          {customer.isActive ? 'აქტიური' : 'დაბლოკილი'}
        </span>
      ),
    },
    {
      key: 'created',
      header: 'რეგისტრაცია',
      render: (customer) => (
        <span className="whitespace-nowrap text-ink-600">{dateOnly(customer.createdAt)}</span>
      ),
    },
  ];

  return (
    <div>
      <header className="mb-4">
        <h1 className="text-lg font-semibold text-ink-900">მომხმარებლები</h1>
        <p className="text-sm text-ink-600">{data ? `${data.total} ჩანაწერი` : 'იტვირთება…'}</p>
      </header>

      <form
        className="mb-3 flex flex-wrap gap-2 rounded-xl border border-ink-200 bg-white p-3"
        onSubmit={(event) => {
          event.preventDefault();
          setParam('q', query.trim());
        }}
      >
        <label className="relative min-w-56 flex-1">
          <span className="sr-only">ძებნა სახელით, ელფოსტით ან ტელეფონით</span>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="სახელი, ელფოსტა ან ტელეფონი"
            className="h-9 w-full rounded-lg border border-ink-300 pl-9 pr-3 text-sm focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/30"
          />
        </label>
        <Select
          aria-label="სტატუსი"
          value={state}
          placeholder="ყველა"
          options={[
            { value: 'active', label: 'აქტიური' },
            { value: 'blocked', label: 'დაბლოკილი' },
          ]}
          onChange={(event) => setParam('state', event.target.value)}
        />
        <Button type="submit" variant="outline" size="sm">
          ძებნა
        </Button>
      </form>

      {error ? (
        <ErrorState title="მომხმარებლები ვერ ჩაიტვირთა" error={error} />
      ) : (
        <>
          <DataTable
            caption="მომხმარებლების სია"
            columns={columns}
            rows={data?.items || []}
            loading={loading}
            empty={<EmptyState title="მომხმარებელი ვერ მოიძებნა" description="შეცვალეთ ფილტრი." />}
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
    </div>
  );
}
