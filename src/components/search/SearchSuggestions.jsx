import { Clock, Search, X } from 'lucide-react';
import ProductImage from '../common/ProductImage.jsx';
import { Skeleton } from '../common/Skeleton.jsx';
import { formatPrice } from '../../utils/format.js';
import { TEXT } from '../../constants/index.js';

/**
 * ძებნის ჩამოსაშლელი, ორ რეჟიმში:
 *
 *   query < 2 სიმბოლო  → ბოლო ძებნები (localStorage-იდან)
 *   query ≥ 2 სიმბოლო  → top-5 შედეგი + „ყველა შედეგის ნახვა“
 *
 * კლავიატურით ნავიგაციას მართავს SearchBar — აქ მხოლოდ `activeIndex` ისმება.
 */
export default function SearchSuggestions({
  mode = 'results',
  results = [],
  recent = [],
  loading = false,
  query = '',
  activeIndex = -1,
  onSelect,
  onSelectRecent,
  onForgetRecent,
  onClearRecent,
  onViewAll,
  listId,
  optionId,
}) {
  const panel =
    'absolute left-0 right-0 top-full z-drawer mt-2 overflow-hidden rounded-card border border-ink-200 bg-white shadow-popover';

  /* ---------------------------------------------------------------- ბოლო ძებნები */
  if (mode === 'recent') {
    return (
      <div className={panel}>
        <div className="flex items-center justify-between gap-2 border-b border-ink-100 px-3 py-2">
          <span className="text-2xs font-bold uppercase tracking-wide text-ink-500">
            {TEXT.recentSearches}
          </span>
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={onClearRecent}
            className="rounded-control px-1.5 py-0.5 text-xs font-semibold text-primary-700 hover:underline"
          >
            {TEXT.clearAll}
          </button>
        </div>

        <ul id={listId} role="listbox" aria-label={TEXT.recentSearches} className="p-1.5">
          {recent.map((term, index) => (
            <li key={term} role="presentation" className="group/item relative">
              <button
                type="button"
                id={index === activeIndex ? optionId : undefined}
                role="option"
                aria-selected={index === activeIndex}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => onSelectRecent(term)}
                className={`flex w-full items-center gap-3 rounded-control py-2 pl-2 pr-9 text-left transition-colors ${
                  index === activeIndex ? 'bg-primary-50' : 'hover:bg-ink-50'
                }`}
              >
                <Clock className="h-4 w-4 shrink-0 text-ink-500" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate text-sm text-ink-800">{term}</span>
              </button>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => onForgetRecent(term)}
                aria-label={`„${term}“ ისტორიიდან წაშლა`}
                className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-control text-ink-500 opacity-0 transition-opacity hover:bg-ink-100 focus-visible:opacity-100 group-hover/item:opacity-100"
              >
                <X className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  /* ------------------------------------------------------------------- შედეგები */
  const hasResults = results.length > 0;
  const viewAllIndex = results.length;

  return (
    <div className={panel}>
      {loading && (
        <ul className="p-2">
          {[0, 1, 2].map((i) => (
            <li key={i} className="flex items-center gap-3 p-2">
              <Skeleton className="h-11 w-11" rounded="rounded-control" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            </li>
          ))}
        </ul>
      )}

      {!loading && !hasResults && query && (
        <div className="px-4 py-6 text-center">
          <Search className="mx-auto mb-2 h-5 w-5 text-ink-500" aria-hidden="true" />
          <p className="text-sm font-medium text-ink-800">„{query}“ — შედეგები ვერ მოიძებნა</p>
          <p className="mt-1 text-xs text-ink-500">სცადეთ სხვა სიტყვა ან ბრენდის სახელი.</p>
        </div>
      )}

      {!loading && hasResults && (
        <ul id={listId} role="listbox" aria-label="ძებნის შედეგები" className="max-h-[60vh] overflow-y-auto p-1.5">
          {results.map((product, index) => (
            <li key={product.id} role="presentation">
              <button
                type="button"
                id={index === activeIndex ? optionId : undefined}
                role="option"
                aria-selected={index === activeIndex}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => onSelect(product)}
                className={`flex w-full items-center gap-3 rounded-control p-2 text-left transition-colors ${
                  index === activeIndex ? 'bg-primary-50' : 'hover:bg-ink-50'
                }`}
              >
                <ProductImage
                  src={product.images?.[0]}
                  alt=""
                  className="h-11 w-11 shrink-0 rounded-control border border-ink-200"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink-900">{product.name}</span>
                  <span className="block truncate text-xs text-ink-500">{product.brand}</span>
                </span>
                <span className="shrink-0 text-sm font-semibold text-ink-900">
                  {formatPrice(product.price)}
                </span>
              </button>
            </li>
          ))}

          <li role="presentation" className="mt-1 border-t border-ink-100 pt-1">
            <button
              type="button"
              id={viewAllIndex === activeIndex ? optionId : undefined}
              role="option"
              aria-selected={viewAllIndex === activeIndex}
              onMouseDown={(e) => e.preventDefault()}
              onClick={onViewAll}
              className={`flex w-full items-center justify-center gap-2 rounded-control p-2.5 text-sm font-semibold text-primary-700 transition-colors ${
                viewAllIndex === activeIndex ? 'bg-primary-50' : 'hover:bg-ink-50'
              }`}
            >
              <Search className="h-4 w-4" aria-hidden="true" />
              {TEXT.viewAllResults}
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}
