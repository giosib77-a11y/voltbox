import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, SlidersHorizontal } from 'lucide-react';
import Breadcrumbs from '../components/common/Breadcrumbs.jsx';
import Button from '../components/common/Button.jsx';
import Modal from '../components/common/Modal.jsx';
import ErrorState from '../components/common/ErrorState.jsx';
import ActiveFilters from '../components/catalog/ActiveFilters.jsx';
import FilterSidebar from '../components/catalog/FilterSidebar.jsx';
import Pagination from '../components/catalog/Pagination.jsx';
import SortSelect from '../components/catalog/SortSelect.jsx';
import ProductGrid from '../components/product/ProductGrid.jsx';
import SearchBar from '../components/search/SearchBar.jsx';
import { useCatalogParams } from '../hooks/useQueryParams.js';
import { useCategories, useProducts } from '../hooks/useProducts.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { countActiveFilters } from '../utils/filter.js';
import { formatItemsCount, formatNumber } from '../utils/format.js';
import { PAGE_SIZE, QUERY_KEYS, SORT_OPTIONS, TEXT } from '../constants/index.js';

/**
 * ძებნის შედეგები. ფილტრები კატეგორიათაშორისია (კატეგორია + ბრენდი),
 * კონფიგი მოდის `mockApi`-ის GLOBAL_FILTERS-იდან — facets-ის key-ებით.
 */
const SEARCH_SORT_OPTIONS = [{ value: 'relevance', label: 'რელევანტურობით' }, ...SORT_OPTIONS];

export default function SearchResults() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get(QUERY_KEYS.search) || '';
  const [sheetOpen, setSheetOpen] = useState(false);
  const { data: categories } = useCategories();

  // ძებნის შედეგები კატეგორიათაშორისია — ფილტრებად კატეგორია და ბრენდი გვრჩება.
  // `optionLabels` აქცევს ტექნიკურ id-ს ("cables") ქართულ სახელად.
  const searchFilters = useMemo(
    () => [
      {
        key: 'category',
        label: 'კატეგორია',
        type: 'checkbox',
        optionLabels: Object.fromEntries((categories || []).map((c) => [c.id, c.name])),
      },
      { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
    ],
    [categories],
  );

  const { filters, sort, page, setFilters, setSort, setPage, clearFilters } =
    useCatalogParams(searchFilters, { defaultSort: 'relevance' });

  const params = useMemo(
    () => ({ q: query, filters, sort: sort, page, limit: PAGE_SIZE }),
    [query, filters, sort, page],
  );

  const { data, loading, error, reload } = useProducts(params, { skip: !query });

  useDocumentTitle(query ? `ძებნა: ${query}` : 'ძებნა');

  const facets = data?.facets || { values: {}, price: { min: 0, max: 0 } };
  const activeCount = countActiveFilters(filters);

  const sidebar = (
    <FilterSidebar
      filters={searchFilters}
      facets={facets}
      active={filters}
      onChange={setFilters}
      onClear={clearFilters}
      loading={loading}
    />
  );

  return (
    <div className="container-page py-5 lg:py-7">
      <Breadcrumbs items={[{ label: 'ძებნა' }]} className="mb-4" />

      <div className="mb-5">
        <h1 className="text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
          {query ? (
            <>
              შედეგები: <span className="text-primary-700">„{query}“</span>
            </>
          ) : (
            'ძებნა'
          )}
        </h1>
        <div className="mt-4 max-w-xl md:hidden">
          <SearchBar defaultValue={query} />
        </div>
      </div>

      {!query ? (
        <div className="rounded-card border border-dashed border-ink-300 bg-white px-6 py-14 text-center">
          <Search className="mx-auto h-8 w-8 text-ink-400" aria-hidden="true" />
          <h2 className="mt-4 text-lg font-semibold text-ink-900">რას ეძებთ?</h2>
          <p className="mt-1.5 text-sm text-ink-600">
            შეიყვანეთ პროდუქტის სახელი, ბრენდი ან მახასიათებელი — მაგალითად „20 000“ ან „USB C 2m“.
          </p>
          <div className="mx-auto mt-6 max-w-md">
            <SearchBar autoFocus />
          </div>
        </div>
      ) : (
        <div className="lg:flex lg:gap-7">
          <aside className="hidden w-60 shrink-0 lg:block">
            <div className="sticky top-[8.5rem] max-h-[calc(100vh-10rem)] overflow-y-auto rounded-card border border-ink-200 bg-white p-4 pr-3">
              {sidebar}
            </div>
          </aside>

          <div className="min-w-0 flex-1">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-ink-600" aria-live="polite">
                {loading ? (
                  <span className="text-ink-500">{TEXT.loading}</span>
                ) : (
                  <>
                    {TEXT.found}{' '}
                    <strong className="text-ink-900">{formatItemsCount(data?.total || 0)}</strong>
                  </>
                )}
              </p>

              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" className="lg:hidden" onClick={() => setSheetOpen(true)}>
                  <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                  {TEXT.filters}
                  {activeCount > 0 && (
                    <span className="ml-0.5 rounded-pill bg-primary-600 px-1.5 text-2xs font-bold text-white">
                      {activeCount}
                    </span>
                  )}
                </Button>
                <SortSelect value={sort} onChange={setSort} options={SEARCH_SORT_OPTIONS} />
              </div>
            </div>

            <ActiveFilters
              filters={searchFilters}
              active={filters}
              onChange={setFilters}
              onClear={clearFilters}
              className="mb-4"
            />

            {error ? (
              <ErrorState error={error} onRetry={reload} />
            ) : (
              <ProductGrid
                products={data?.items || []}
                loading={loading}
                skeletonCount={PAGE_SIZE}
                emptyProps={{
                  icon: Search,
                  title: `„${query}“ — შედეგები ვერ მოიძებნა`,
                  description: 'შეამოწმეთ მართლწერა ან სცადეთ უფრო ზოგადი სიტყვა.',
                  actionLabel: TEXT.backToShop,
                  actionTo: '/',
                }}
              />
            )}

            {!loading && !error && (data?.totalPages || 1) > 1 && (
              <Pagination page={data.page} totalPages={data.totalPages} onChange={setPage} className="mt-8" />
            )}
          </div>
        </div>
      )}

      <Modal
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        position="bottom"
        title={`${TEXT.filters}${activeCount > 0 ? ` (${activeCount})` : ''}`}
        footer={
          <div className="flex gap-3">
            <Button variant="outline" fullWidth onClick={() => { clearFilters(); setSheetOpen(false); }}>
              {TEXT.clearAll}
            </Button>
            <Button fullWidth onClick={() => setSheetOpen(false)}>
              ჩვენება ({formatNumber(data?.total || 0)})
            </Button>
          </div>
        }
      >
        <div className="px-5 py-1">{sidebar}</div>
      </Modal>
    </div>
  );
}
