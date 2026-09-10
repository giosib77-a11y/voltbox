import { X } from 'lucide-react';
import { buildFilterChips, toggleFilterValue } from '../../utils/filter.js';
import { TEXT } from '../../constants/index.js';

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
            className="group inline-flex items-center gap-1.5 rounded-pill border border-ink-200 bg-white py-1 pl-3 pr-2 text-xs font-medium text-ink-700 transition-colors hover:border-danger-300 hover:bg-danger-50 hover:text-danger-700"
          >
            <span className="text-ink-500 group-hover:text-danger-500">{chip.groupLabel}:</span>
            {chip.label}
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="sr-only">ფილტრის მოხსნა</span>
          </button>
        </li>
      ))}

      <li>
        <button
          type="button"
          onClick={onClear}
          className="rounded-pill px-2.5 py-1 text-xs font-semibold text-primary-700 underline-offset-2 hover:underline"
        >
          {TEXT.clearAll}
        </button>
      </li>
    </ul>
  );
}
