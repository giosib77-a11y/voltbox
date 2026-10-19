import { X } from 'lucide-react';
import { buildFilterChips, toggleFilterValue } from '../../utils/filter.js';
import { t } from '../../i18n/index.js';

/**
 * აქტიური ფილტრების chip-ები — ცალ-ცალკე მოხსნით და საერთო გასუფთავებით.
 */
export default function ActiveFilters({ filters = [], active = {}, onChange, onClear, className = '' }) {
  const chips = buildFilterChips(active, filters);
  if (chips.length === 0) return null;

  function handleRemove(chip) {
    if (chip.key === 'price') {
      const next = { ...active };
      delete next.price;
      onChange(next);
      return;
    }
    const config = filters.find((f) => f.key === chip.key);
    if (!config) return;
    onChange(toggleFilterValue(active, config, chip.value));
  }

  return (
    <ul className={`flex flex-wrap items-center gap-2 ${className}`}>
      {chips.map((chip) => (
        <li key={chip.id}>
          <button
            type="button"
            onClick={() => handleRemove(chip)}
            className="group inline-flex items-center gap-1.5 rounded-pill border border-primary-200 bg-primary-50 py-1 pl-3 pr-2 text-xs font-medium text-primary-800 transition-colors hover:border-primary-500 hover:bg-primary-100"
          >
            <span className="text-ink-500">{chip.groupLabel}:</span>
            {chip.label}
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="sr-only">{t('filters.remove')}</span>
          </button>
        </li>
      ))}

      <li>
        <button
          type="button"
          onClick={onClear}
          className="rounded-pill px-2.5 py-1 text-xs font-semibold text-primary-700 underline-offset-2 hover:underline"
        >
          {t('common.clearAll')}
        </button>
      </li>
    </ul>
  );
}
