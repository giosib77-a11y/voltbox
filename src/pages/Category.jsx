import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { PackageSearch, SlidersHorizontal } from 'lucide-react';
import Breadcrumbs from '../components/common/Breadcrumbs.jsx';
import Button from '../components/common/Button.jsx';
import Modal from '../components/common/Modal.jsx';
import EmptyState from '../components/common/EmptyState.jsx';
import ErrorState from '../components/common/ErrorState.jsx';
import ActiveFilters from '../components/catalog/ActiveFilters.jsx';
import FilterSidebar from '../components/catalog/FilterSidebar.jsx';
import Pagination from '../components/catalog/Pagination.jsx';
import SortSelect from '../components/catalog/SortSelect.jsx';
import ProductGrid from '../components/product/ProductGrid.jsx';
import { useCatalogParams } from '../hooks/useQueryParams.js';
import { useCategories, useProducts } from '../hooks/useProducts.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { countActiveFilters } from '../utils/filter.js';
import { formatItemsCount, formatNumber } from '../utils/format.js';
import { PAGE_SIZE, TEXT } from '../constants/index.js';

/**
 * კატეგორიის გვერდი.
 * ფილტრები, სორტი და გვერდი მთლიანად URL-ში ცხოვრობს (useCatalogParams).
 */
export default function Category() {
  const { slug } = useParams();
  const { data: categories, loading: categoriesLoading } = useCategories();
  const [sheetOpen, setSheetOpen] = useState(false);

  const category = useMemo(
    () => (categories || []).find((c) => c.slug === slug) || null,
    [categories, slug],
  );

  const categoryFilters = useMemo(() => category?.filters || [], [category]);
  const { filters, sort, page, setFilters, setSort, setPage, clearFilters } =
    useCatalogParams(categoryFilters);

  const params = useMemo(
    () => ({ category: slug, filters, sort, page, limit: PAGE_SIZE }),
    [slug, filters, sort, page],
  );

  const { data, loading, error, reload } = useProducts(params, { skip: !category });

  useDocumentTitle(category ? category.name : 'კატალოგი');


  if (!categoriesLoading && !category) {
    return (
      <div className="container-page py-16">
        <EmptyState
          title="კატეგორია ვერ მოიძებნა"
          description="შესაძლოა მისამართი შეიცვალა ან კატეგორია აღარ არსებობს."
          actionLabel={TEXT.backToShop}
          actionTo="/"
        />
      </div>
    );
  }

  const facets = data?.facets || { values: {}, price: { min: 0, max: 0 } };
  const activeCount = countActiveFilters(filters);
  const items = data?.items || [];

  const sidebar = (
    <FilterSidebar
      filters={categoryFilters}
      facets={facets}
      active={filters}
      onChange={setFilters}
      onClear={clearFilters}
      loading={loading}
    />
  );

  return (
    <div className="container-page py-5 lg:py-7">
      <Breadcrumbs items={[{ label: category?.name || '…' }]} className="mb-4" />

      <header className="mb-5">
        <h1 className="text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
          {category?.name || '…'}
        </h1>
        {category?.description && (
          <p className="mt-1.5 max-w-2xl text-sm text-ink-600">{category.description}</p>
        )}
      </header>

      <div className="lg:flex lg:gap-7">
        <aside className="hidden w-64 shrink-0 lg:block">
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
              <Button
                variant="outline"
                size="sm"
                className="lg:hidden"
                onClick={() => setSheetOpen(true)}
              >
                <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                {TEXT.filters}
                {activeCount > 0 && (
                  <span className="ml-0.5 rounded-pill bg-primary-600 px-1.5 text-2xs font-bold text-white">
                    {activeCount}
                  </span>
                )}
              </Button>
              <SortSelect value={sort} onChange={setSort} />
            </div>
          </div>

          <ActiveFilters
            filters={categoryFilters}
            active={filters}
            onChange={setFilters}
            onClear={clearFilters}
            className="mb-4"
          />

          {error ? (
            <ErrorState error={error} onRetry={reload} />
          ) : (
            <ProductGrid
              products={items}
              loading={loading || categoriesLoading}
              skeletonCount={PAGE_SIZE}
              emptyProps={{
                icon: PackageSearch,
                title: 'ამ ფილტრებით პროდუქტი ვერ მოიძებნა',
                description: 'შეამცირეთ ფილტრების რაოდენობა ან გაასუფთავეთ ისინი.',
                actionLabel: activeCount > 0 ? TEXT.clearFilters : TEXT.backToShop,
                onAction: activeCount > 0 ? clearFilters : undefined,
                actionTo: activeCount > 0 ? undefined : '/',
              }}
            />
          )}

          {!loading && !error && (data?.totalPages || 1) > 1 && (
            <Pagination
              page={data.page}
              totalPages={data.totalPages}
              onChange={setPage}
              className="mt-8"
            />
          )}
        </div>
      </div>

      <Modal
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        position="bottom"
        title={`${TEXT.filters}${activeCount > 0 ? ` (${activeCount})` : ''}`}
        footer={
          <div className="flex gap-3">
            <Button
              variant="outline"
              fullWidth
              onClick={() => {
                clearFilters();
                setSheetOpen(false);
              }}
            >
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
