import { useMemo, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { COLOR_SWATCHES } from '../../constants/index.js';
import { formatNumber } from '../../utils/format.js';

/**
 * ერთი ფილტრის ჯგუფი. ტიპს კარნახობს კონფიგი (`categories.js`) —
 * აქ არავითარი კატეგორია-სპეციფიკური ლოგიკა არ არის.
 *
 * @param {{ config: import('../../types.js').CategoryFilter, counts: Record<string, number> }} props
 */

const VISIBLE_LIMIT = 6;

export default function FilterGroup({ config, counts = {}, value, onToggle }) {
  const labelFor = (optionValue) => config.optionLabels?.[optionValue] ?? optionValue;
  const [expanded, setExpanded] = useState(true);
  const [showAll, setShowAll] = useState(false);

  const options = useMemo(() => Object.entries(counts), [counts]);
  const selected = Array.isArray(value) ? value : [];

  if (config.type !== 'toggle' && options.length === 0) return null;

  const visible = showAll ? options : options.slice(0, VISIBLE_LIMIT);
  const selectedCount = config.type === 'toggle' ? (value === true ? 1 : 0) : selected.length;
  const panelId = `filter-panel-${config.key.replace(/\W/g, '-')}`;

  return (
    <div className="border-b border-ink-200 py-4 last:border-b-0">
      <h3>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-controls={panelId}
          className="flex w-full items-center justify-between gap-2 text-left"
        >
          <span className="text-sm font-semibold text-ink-900">
            {config.label}
            {selectedCount > 0 && (
              <span className="ml-1.5 rounded-pill bg-primary-100 px-1.5 py-0.5 text-2xs font-bold text-primary-700">
                {selectedCount}
              </span>
            )}
          </span>
          <ChevronDown
            className={`h-4 w-4 shrink-0 text-ink-500 transition-transform ${expanded ? '' : '-rotate-90'}`}
            aria-hidden="true"
          />
        </button>
      </h3>

      <div id={panelId} hidden={!expanded} className="mt-3">
        {config.type === 'toggle' && <ToggleControl config={config} counts={counts} value={value} onToggle={onToggle} />}

        {config.type === 'swatch' && (
          <SwatchControl
            options={visible}
            selected={selected}
            config={config}
            onToggle={onToggle}
            labelFor={labelFor}
          />
        )}

        {config.type !== 'toggle' && config.type !== 'swatch' && (
          <CheckboxControl
            options={visible}
            selected={selected}
            config={config}
            onToggle={onToggle}
            labelFor={labelFor}
          />
        )}

        {config.type !== 'toggle' && options.length > VISIBLE_LIMIT && (
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="mt-2.5 text-xs font-semibold text-primary-700 underline-offset-2 hover:underline"
          >
            {showAll ? 'ნაკლების ჩვენება' : `კიდევ ${options.length - VISIBLE_LIMIT} ვარიანტი`}
          </button>
        )}
      </div>
    </div>
  );
}

function CheckboxControl({ options, selected, config, onToggle, labelFor }) {
  return (
    <ul className="space-y-0.5">
      {options.map(([optionValue, count]) => {
        const isChecked = selected.includes(optionValue);
        const isDisabled = count === 0 && !isChecked;

        return (
          <li key={optionValue}>
            <label
              className={`flex cursor-pointer items-center gap-2.5 rounded-control px-2 py-1.5 transition-colors ${
                isDisabled ? 'cursor-not-allowed opacity-45' : 'hover:bg-ink-50'
              }`}
            >
              <span
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
                  isChecked ? 'border-primary-600 bg-primary-600' : 'border-ink-300 bg-white'
                }`}
              >
                {isChecked && <Check className="h-3 w-3 text-white" aria-hidden="true" />}
              </span>
              <input
                type="checkbox"
                className="sr-only"
                checked={isChecked}
                disabled={isDisabled}
                onChange={() => onToggle(config, optionValue)}
              />
              <span className="min-w-0 flex-1 truncate text-sm text-ink-700">{labelFor(optionValue)}</span>
              <span className="shrink-0 text-xs tabular-nums text-ink-500">{formatNumber(count)}</span>
            </label>
          </li>
        );
      })}
    </ul>
  );
}

function SwatchControl({ options, selected, config, onToggle, labelFor }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {options.map(([optionValue, count]) => {
        const isChecked = selected.includes(optionValue);
        const isDisabled = count === 0 && !isChecked;
        const color = COLOR_SWATCHES[optionValue] || '#cbd2dd';

        return (
          <li key={optionValue}>
            <button
              type="button"
              disabled={isDisabled}
              onClick={() => onToggle(config, optionValue)}
              aria-pressed={isChecked}
              title={`${labelFor(optionValue)} (${count})`}
              className={`flex h-9 items-center gap-2 rounded-pill border px-2.5 text-xs transition-all ${
                isChecked
                  ? 'border-primary-600 bg-primary-50 font-semibold text-primary-800'
                  : 'border-ink-200 bg-white text-ink-700 hover:border-ink-300'
              } ${isDisabled ? 'cursor-not-allowed opacity-40' : ''}`}
            >
              <span
                className="h-4 w-4 shrink-0 rounded-full ring-1 ring-inset ring-ink-950/15"
                style={{ backgroundColor: color }}
                aria-hidden="true"
              />
              {labelFor(optionValue)}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function ToggleControl({ config, counts, value, onToggle }) {
  const count = Object.values(counts)[0] ?? 0;
  const isOn = value === true;

  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-control px-2 py-1.5 hover:bg-ink-50">
      <span className="text-sm text-ink-700">
        მხოლოდ {config.label}
        <span className="ml-1.5 text-xs text-ink-500">({formatNumber(count)})</span>
      </span>
      <input
        type="checkbox"
        className="sr-only"
        checked={isOn}
        onChange={() => onToggle(config, true)}
      />
      <span
        aria-hidden="true"
        className={`relative h-6 w-11 shrink-0 rounded-pill transition-colors ${
          isOn ? 'bg-primary-600' : 'bg-ink-300'
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-all ${
            isOn ? 'left-[1.375rem]' : 'left-0.5'
          }`}
        />
      </span>
    </label>
  );
}
