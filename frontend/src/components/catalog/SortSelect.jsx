import { ArrowUpDown } from 'lucide-react';
import { SORT_OPTIONS } from '../../constants/index.js';
import { t } from '../../i18n/index.js';

/**
 * სორტირების არჩევანი. ცვლილება დაუყოვნებლივ აისახება URL-ში.
 * `options` are values; each one's label is `sort.<value>`.
 */
export default function SortSelect({ value, onChange, options = SORT_OPTIONS, className = '' }) {
  return (
    <div className={`relative ${className}`}>
      <label htmlFor="sort-select" className="sr-only">
        {t('common.sort')}
      </label>
      <ArrowUpDown
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500"
        aria-hidden="true"
      />
      <select
        id="sort-select"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="field-text h-10 w-full appearance-none rounded-control border border-ink-300 bg-surface pl-9 pr-8 font-medium text-ink-800 transition-colors hover:border-ink-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30 sm:w-auto"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {t(`sort.${option}`)}
          </option>
        ))}
      </select>
    </div>
  );
}
