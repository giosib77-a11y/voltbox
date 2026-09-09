import { SlidersHorizontal } from 'lucide-react';
import FilterGroup from './FilterGroup.jsx';
import PriceRangeSlider from './PriceRangeSlider.jsx';
import Button from '../common/Button.jsx';
import { countActiveFilters, toggleFilterValue } from '../../utils/filter.js';
import { TEXT } from '../../constants/index.js';

/**
 * გენერიკული ფილტრების პანელი.
 *
 * არაფერი იცის კონკრეტული კატეგორიის შესახებ — მთლიანად `filters` კონფიგზე
 * და `facets`-ზე მუშაობს. ახალი კატეგორიის დამატება მოითხოვს მხოლოდ
 * `data/categories.js`-ში ჩანაწერს.
 *
 * @param {{
 *   filters: import('../../types.js').CategoryFilter[],
 *   facets: { values: Record<string, Record<string, number>>, price: { min:number, max:number } },
 *   active: object,
 *   onChange: (next: object) => void,
 *   onClear: () => void
 * }} props
 */
export default function FilterSidebar({
  filters = [],
  facets = { values: {}, price: { min: 0, max: 0 } },
  active = {},
  onChange,
  onClear,
  loading = false,
  className = '',
}) {
  const activeCount = countActiveFilters(active);

  function handleToggle(config, value) {
    onChange(toggleFilterValue(active, config, value));
  }

  function handlePriceChange(range) {
    const next = { ...active };
    if (range) next.price = range;
    else delete next.price;
    onChange(next);
  }

  return (
    <div className={className}>
      <div className="mb-1 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-ink-900">
          <SlidersHorizontal className="h-4 w-4 text-ink-500" aria-hidden="true" />
          {TEXT.filters}
        </h2>
        {activeCount > 0 && (
          <Button variant="link" size="xs" onClick={onClear} className="px-0">
            {TEXT.clearAll}
          </Button>
        )}
      </div>

      <div
        className={loading ? 'pointer-events-none opacity-60 transition-opacity' : 'transition-opacity'}
      >
        <PriceRangeSlider
          min={facets.price?.min ?? 0}
          max={facets.price?.max ?? 0}
          value={active.price ?? null}
          onChange={handlePriceChange}
        />

        {filters.map((config) => (
          <FilterGroup
            key={config.key}
            config={config}
            counts={facets.values?.[config.key] || {}}
            value={active[config.key]}
            onToggle={handleToggle}
          />
        ))}
      </div>
    </div>
  );
}
