/**
 * ProductList: the admin's product table.
 *
 * What it does: search, filters, sort and pagination over GET /admin/products.
 * Where it fits: /admin/products.
 * Notes: every control lives in the URL query string, so the back button works
 * and a filtered view can be pasted to a colleague. Search is debounced, because
 * one request per keystroke is both slow and pointless.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Copy, Plus, Search, Trash2 } from 'lucide-react';

import Button from '../../components/common/Button.jsx';
import EmptyState from '../../components/common/EmptyState.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import Select from '../../components/common/Select.jsx';
import ProductImage from '../../components/common/ProductImage.jsx';
import DataTable from '../components/DataTable.jsx';
import AdminPagination from '../components/AdminPagination.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import { ProductStatusBadge, StockBadge } from '../components/StatusBadge.jsx';
import { dateOnly, money } from '../format.js';
import * as adminApi from '../adminApi.js';
import { useDebounce } from '../../hooks/useDebounce.js';

const SORTS = [
  { value: 'created_desc', label: 'ახლები პირველად' },
  { value: 'created_asc', label: 'ძველები პირველად' },
  { value: 'name_asc', label: 'სახელი ა–ჰ' },
  { value: 'name_desc', label: 'სახელი ჰ–ა' },
  { value: 'price_asc', label: 'ფასი ზრდადობით' },
  { value: 'price_desc', label: 'ფასი კლებადობით' },
  { value: 'stock_asc', label: 'მარაგი ზრდადობით' },
];

const LIMIT = 20;

export default function ProductList() {
  const [params, setParams] = useSearchParams();

  const page = Number(params.get('page') || 1);
  const sort = params.get('sort') || 'created_desc';
  const categoryId = params.get('categoryId') || '';
  const brandId = params.get('brandId') || '';
  const status = params.get('status') || '';
  const lowStock = params.get('lowStock') === 'true';
  const search = params.get('q') || '';

  const [query, setQuery] = useState(search);
  const debouncedQuery = useDebounce(query, 300);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [duplicating, setDuplicating] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteError, setDeleteError] = useState(null);
  const [reloadToken, setReloadToken] = useState(0);

  /** Writes one control into the URL and returns to page 1. */
  const setParam = useCallback(
    (key, value) => {
      const next = new URLSearchParams(params);
      if (value === '' || value === null || value === false) next.delete(key);
      else next.set(key, String(value));
      if (key !== 'page') next.delete('page');
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  // The settled search term is a control like any other and belongs in the URL -
  // but only once it has settled, or every keystroke would become a history entry.
  useEffect(() => {
    if (search !== debouncedQuery) setParam('q', debouncedQuery);
    // setParam changes on every render of params; depending on it would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery]);

  useEffect(() => {
    Promise.all([adminApi.listCategories(), adminApi.listBrands()])
      .then(([nextCategories, nextBrands]) => {
        setCategories(nextCategories);
        setBrands(nextBrands);
      })
      .catch(() => {
        // Filter options are a convenience; the table still works without them.
      });
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    adminApi
      .listProducts({
        page,
        limit: LIMIT,
        sort,
        q: search || undefined,
        categoryId: categoryId || undefined,
        brandId: brandId || undefined,
        isActive: status === 'active' ? true : status === 'inactive' ? false : undefined,
        includeArchived: status === 'archived' ? true : undefined,
        lowStock: lowStock || undefined,
      })
      .then((result) => {
        if (cancelled) return;
        // The API either hides archived rows or includes them; "archived only"
        // is a view of that, filtered here rather than adding a server flag.
        const items =
          status === 'archived' ? result.items.filter((item) => item.archivedAt) : result.items;
        setData({ ...result, items });
      })
      .catch((caught) => {
        if (!cancelled) setError(caught);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [page, sort, search, categoryId, brandId, status, lowStock, reloadToken]);

  async function handleDuplicate(product) {
    setDuplicating(product.id);
    try {
      await adminApi.duplicateProduct(product.id);
      setReloadToken((token) => token + 1);
    } finally {
      setDuplicating(null);
    }
  }

  /**
   * Deleting is permanent and the server may refuse it.
   *
   * A product that appears in an order cannot go - removing it would rewrite
   * what a customer actually bought. The API answers 409 PRODUCT_IN_USE there,
   * and the dialog turns that refusal into an offer to archive instead, which
   * is what the admin wanted in the first place.
   */
  async function handleDelete() {
    setDeleteError(null);
    try {
      await adminApi.deleteProduct(deleting.id);
      setDeleting(null);
      setReloadToken((token) => token + 1);
    } catch (caught) {
      setDeleteError(caught);
    }
  }

  async function handleArchiveInstead() {
    try {
      await adminApi.archiveProduct(deleting.id);
      closeDelete();
      setReloadToken((token) => token + 1);
    } catch (caught) {
      setDeleteError(caught);
    }
  }

  function closeDelete() {
    setDeleting(null);
    setDeleteError(null);
  }

  const blockedByOrders = deleteError?.details?.code === 'PRODUCT_IN_USE';
  const ordersCount = deleteError?.details?.details?.ordersCount;

  // Three states in one dialog: the warning before, a refusal that offers the
  // way out, and any other server error verbatim.
  let deleteDescription;
  if (blockedByOrders) {
    deleteDescription = `„${deleting?.name}“ უკვე გაყიდულია (${ordersCount} შეკვეთა), ამიტომ სამუდამოდ ვერ წაიშლება — შეკვეთის ისტორია არ უნდა შეიცვალოს. არქივში გადატანა პროდუქტს მაღაზიიდან მალავს და ისტორიას ხელუხლებლად ტოვებს.`;
  } else if (deleteError) {
    deleteDescription = deleteError.message;
  } else {
    deleteDescription = `„${deleting?.name}“ სამუდამოდ წაიშლება — სურათებთან და მარაგის ისტორიასთან ერთად. ქმედება შეუქცევადია. თუ პროდუქტი მხოლოდ დროებით უნდა დამალოთ, არქივში გადატანა სჯობს.`;
  }

  const columns = useMemo(
    () => [
      {
        key: 'name',
        header: 'პროდუქტი',
        render: (product) => (
          <div className="flex items-center gap-3">
            <ProductImage
              src={product.primaryImage}
              alt=""
              className="h-10 w-10 shrink-0 rounded-lg object-cover"
            />
            <div className="min-w-0">
              <Link
                to={`/admin/products/${product.id}`}
                className="block truncate font-medium text-ink-900 hover:text-accent-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700"
              >
                {product.name}
              </Link>
              <span className="text-xs text-ink-500">{product.sku || product.slug}</span>
            </div>
          </div>
        ),
      },
      {
        key: 'category',
        header: 'კატეგორია',
        render: (product) => (
          <span className="text-ink-700">
            {product.categoryName}
            <span className="block text-xs text-ink-500">{product.brandName}</span>
          </span>
        ),
      },
      {
        key: 'price',
        header: 'ფასი',
        align: 'right',
        render: (product) => (
          <span className="tabular-nums">
            {money(product.price)}
            {product.oldPrice ? (
              <span className="block text-xs text-ink-500 line-through">
                {money(product.oldPrice)}
              </span>
            ) : null}
          </span>
        ),
      },
      {
        key: 'stock',
        header: 'მარაგი',
        align: 'right',
        render: (product) => <StockBadge status={product.stockStatus} stock={product.stock} />,
      },
      {
        key: 'status',
        header: 'სტატუსი',
        render: (product) => <ProductStatusBadge product={product} />,
      },
      {
        key: 'created',
        header: 'დამატებული',
        render: (product) => (
          <span className="whitespace-nowrap text-ink-600">{dateOnly(product.createdAt)}</span>
        ),
      },
      {
        key: 'actions',
        header: '',
        align: 'right',
        render: (product) => (
          <span className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="xs"
              onClick={() => handleDuplicate(product)}
              loading={duplicating === product.id}
              aria-label={`${product.name} — ასლის შექმნა`}
            >
              <Copy className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="xs"
              onClick={() => {
                setDeleteError(null);
                setDeleting(product);
              }}
              aria-label={`${product.name} — წაშლა`}
            >
              <Trash2 className="h-4 w-4 text-danger-600" aria-hidden="true" />
            </Button>
          </span>
        ),
      },
    ],
    // Only the busy row affects the rendered columns.
    [duplicating],
  );

  return (
    <div>
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-ink-900">პროდუქტები</h1>
          <p className="text-sm text-ink-600">{data ? `${data.total} ჩანაწერი` : 'იტვირთება…'}</p>
        </div>
        <Button to="/admin/products/new" variant="accent" size="sm">
          <Plus className="h-4 w-4" aria-hidden="true" />
          ახალი პროდუქტი
        </Button>
      </header>

      <div className="mb-3 grid gap-2 rounded-xl border border-ink-200 bg-white p-3 lg:grid-cols-[1fr_auto_auto_auto_auto]">
        <label className="relative">
          <span className="sr-only">ძებნა სახელით, SKU-თი ან slug-ით</span>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="ძებნა სახელით, SKU-თი ან slug-ით"
            className="h-9 w-full rounded-lg border border-ink-300 pl-9 pr-3 text-sm focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/30"
          />
        </label>

        <Select
          aria-label="კატეგორია"
          value={categoryId}
          onChange={(event) => setParam('categoryId', event.target.value)}
          placeholder="ყველა კატეგორია"
          options={categories.map((item) => ({ value: item.id, label: item.name }))}
        />
        <Select
          aria-label="ბრენდი"
          value={brandId}
          onChange={(event) => setParam('brandId', event.target.value)}
          placeholder="ყველა ბრენდი"
          options={brands.map((item) => ({ value: item.id, label: item.name }))}
        />
        <Select
          aria-label="სტატუსი"
          value={status}
          onChange={(event) => setParam('status', event.target.value)}
          placeholder="ყველა სტატუსი"
          options={[
            { value: 'active', label: 'აქტიური' },
            { value: 'inactive', label: 'გამორთული' },
            { value: 'archived', label: 'არქივში' },
          ]}
        />
        <Select
          aria-label="დალაგება"
          value={sort}
          onChange={(event) => setParam('sort', event.target.value)}
          options={SORTS}
        />
      </div>

      <label className="mb-3 flex w-fit items-center gap-2 text-sm text-ink-700">
        <input
          type="checkbox"
          checked={lowStock}
          onChange={(event) => setParam('lowStock', event.target.checked)}
          className="h-4 w-4 rounded border-ink-300 text-accent-600 focus:ring-accent-600/30"
        />
        მხოლოდ ამოწურვადი მარაგი
      </label>

      {error ? (
        <ErrorState
          title="პროდუქტების ჩატვირთვა ვერ მოხერხდა"
          error={error}
          onRetry={() => setReloadToken((token) => token + 1)}
        />
      ) : (
        <>
          <DataTable
            caption="პროდუქტების სია"
            columns={columns}
            rows={data?.items || []}
            loading={loading}
            empty={
              <EmptyState
                title="პროდუქტი ვერ მოიძებნა"
                description="შეცვალეთ ფილტრები ან დაამატეთ ახალი პროდუქტი."
                actionLabel="ახალი პროდუქტი"
                actionTo="/admin/products/new"
              />
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
        title={blockedByOrders ? 'წაშლა შეუძლებელია' : 'პროდუქტის წაშლა'}
        description={deleteDescription}
        confirmLabel={blockedByOrders ? 'არქივში გადატანა' : 'სამუდამოდ წაშლა'}
        variant={blockedByOrders ? 'accent' : 'danger'}
        onConfirm={blockedByOrders ? handleArchiveInstead : handleDelete}
        onClose={closeDelete}
      />
    </div>
  );
}
