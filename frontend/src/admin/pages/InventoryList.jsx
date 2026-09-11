/**
 * InventoryList: stock levels and adjustments.
 *
 * What it does: shows current stock with its status, opens an adjustment dialog
 * and shows a product's movement history.
 * Where it fits: /admin/inventory.
 * Notes: only the reasons an administrator may choose appear in the dialog.
 * The system ones (order_placed, initial) are written by the code that causes
 * them; offering them here would let someone claim an order caused a change
 * that no order caused.
 */

import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { History, Search, SlidersHorizontal } from 'lucide-react';

import Button from '../../components/common/Button.jsx';
import Input from '../../components/common/Input.jsx';
import Select from '../../components/common/Select.jsx';
import Textarea from '../../components/common/Textarea.jsx';
import Modal from '../../components/common/Modal.jsx';
import EmptyState from '../../components/common/EmptyState.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import DataTable from '../components/DataTable.jsx';
import AdminPagination from '../components/AdminPagination.jsx';
import { StockBadge } from '../components/StatusBadge.jsx';
import { MANUAL_REASONS, MOVEMENT_REASONS, REASONS_NEEDING_NOTE } from '../statuses.jsx';
import { dateTime } from '../format.js';
import * as adminApi from '../adminApi.js';

const LIMIT = 20;

function AdjustDialog({ row, onClose, onSaved }) {
  const [change, setChange] = useState('');
  const [reason, setReason] = useState('restock');
  const [note, setNote] = useState('');
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const noteRequired = REASONS_NEEDING_NOTE.includes(reason);

  async function handleSubmit(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      await adminApi.adjustStock(row.productId, {
        change: Number(change),
        reason,
        note: note.trim() || null,
      });
      onSaved();
    } catch (caught) {
      setError(caught);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={`მარაგი — ${row.name}`}>
      <form onSubmit={handleSubmit} noValidate className="space-y-3 p-5">
        {error ? (
          <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
            {error.message}
          </p>
        ) : null}
        <p className="text-sm text-ink-600">
          მიმდინარე მარაგი: <strong className="tabular-nums text-ink-900">{row.stock}</strong>
        </p>
        <Input
          label="ცვლილება"
          hint="დადებითი ამატებს, უარყოფითი აკლებს"
          inputMode="numeric"
          required
          value={change}
          onChange={(event) => setChange(event.target.value)}
        />
        <Select
          label="მიზეზი"
          value={reason}
          options={MANUAL_REASONS.map((value) => ({ value, label: MOVEMENT_REASONS[value] }))}
          onChange={(event) => setReason(event.target.value)}
        />
        <Textarea
          label={noteRequired ? 'კომენტარი (სავალდებულო)' : 'კომენტარი'}
          rows={2}
          required={noteRequired}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>
            გაუქმება
          </Button>
          <Button
            type="submit"
            variant="accent"
            size="sm"
            loading={saving}
            disabled={!change || Number(change) === 0}
          >
            შენახვა
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function HistoryDialog({ row, onClose }) {
  const [movements, setMovements] = useState(null);

  useEffect(() => {
    adminApi
      .listMovements(row.productId, { limit: 50 })
      .then((result) => setMovements(result.items))
      .catch(() => setMovements([]));
  }, [row.productId]);

  return (
    <Modal open onClose={onClose} title={`ისტორია — ${row.name}`}>
      <div className="p-5">
        {movements === null ? (
          <p className="text-sm text-ink-600">იტვირთება…</p>
        ) : movements.length === 0 ? (
          <p className="text-sm text-ink-600">ჩანაწერი არ არის.</p>
        ) : (
          <ol className="max-h-96 space-y-2 overflow-y-auto text-sm">
            {movements.map((movement) => (
              <li key={movement.id} className="flex items-baseline justify-between gap-3">
                <span>
                  <strong
                    className={`tabular-nums ${movement.change > 0 ? 'text-success-700' : 'text-danger-700'}`}
                  >
                    {movement.change > 0 ? '+' : ''}
                    {movement.change}
                  </strong>{' '}
                  <span className="text-ink-700">
                    {MOVEMENT_REASONS[movement.reason] || movement.reason}
                  </span>
                  {movement.note ? <span className="text-ink-500"> — {movement.note}</span> : null}
                  <span className="block text-xs text-ink-500">
                    {movement.previousStock} → {movement.newStock}
                  </span>
                </span>
                <span className="whitespace-nowrap text-xs text-ink-500">
                  {dateTime(movement.createdAt)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </Modal>
  );
}

export default function InventoryList() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get('page') || 1);
  const only = params.get('only') || '';

  const [query, setQuery] = useState(params.get('q') || '');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [adjusting, setAdjusting] = useState(null);
  const [viewingHistory, setViewingHistory] = useState(null);
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

  const search = params.get('q') || '';

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    adminApi
      .listInventory({ page, limit: LIMIT, q: search || undefined, only: only || undefined })
      .then((result) => !cancelled && setData(result))
      .catch((caught) => !cancelled && setError(caught))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [page, search, only, reloadToken]);

  const columns = [
    {
      key: 'name',
      header: 'პროდუქტი',
      render: (row) => (
        <span>
          <span className="block text-ink-900">{row.name}</span>
          <span className="text-xs text-ink-500">{row.sku || '—'}</span>
        </span>
      ),
    },
    {
      key: 'stock',
      header: 'მარაგი',
      align: 'right',
      render: (row) => <StockBadge status={row.stockStatus} stock={row.stock} />,
    },
    {
      key: 'threshold',
      header: 'ზღვარი',
      align: 'right',
      render: (row) => <span className="tabular-nums text-ink-600">{row.lowStockThreshold}</span>,
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (row) => (
        <span className="flex justify-end gap-1">
          <Button variant="ghost" size="xs" onClick={() => setViewingHistory(row)} aria-label="ისტორია">
            <History className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button variant="outline" size="xs" onClick={() => setAdjusting(row)}>
            <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
            კორექტირება
          </Button>
        </span>
      ),
    },
  ];

  return (
    <div>
      <header className="mb-4">
        <h1 className="text-lg font-semibold text-ink-900">მარაგი</h1>
        <p className="text-sm text-ink-600">{data ? `${data.total} პროდუქტი` : 'იტვირთება…'}</p>
      </header>

      <form
        className="mb-3 flex flex-wrap gap-2 rounded-xl border border-ink-200 bg-white p-3"
        onSubmit={(event) => {
          event.preventDefault();
          setParam('q', query.trim());
        }}
      >
        <label className="relative min-w-56 flex-1">
          <span className="sr-only">ძებნა სახელით ან SKU-თი</span>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="ძებნა სახელით ან SKU-თი"
            className="h-9 w-full rounded-lg border border-ink-300 pl-9 pr-3 text-sm focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/30"
          />
        </label>
        <Select
          aria-label="ფილტრი"
          value={only}
          placeholder="ყველა"
          options={[
            { value: 'low', label: 'იწურება' },
            { value: 'out', label: 'ამოწურულია' },
          ]}
          onChange={(event) => setParam('only', event.target.value)}
        />
        <Button type="submit" variant="outline" size="sm">
          ძებნა
        </Button>
      </form>

      {error ? (
        <ErrorState title="მარაგი ვერ ჩაიტვირთა" error={error} />
      ) : (
        <>
          <DataTable
            caption="მარაგის სია"
            columns={columns}
            rows={data?.items || []}
            rowKey={(row) => row.productId}
            loading={loading}
            empty={<EmptyState title="პროდუქტი ვერ მოიძებნა" description="შეცვალეთ ფილტრი." />}
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

      {adjusting ? (
        <AdjustDialog
          row={adjusting}
          onClose={() => setAdjusting(null)}
          onSaved={() => {
            setAdjusting(null);
            setReloadToken((token) => token + 1);
          }}
        />
      ) : null}

      {viewingHistory ? (
        <HistoryDialog row={viewingHistory} onClose={() => setViewingHistory(null)} />
      ) : null}
    </div>
  );
}
