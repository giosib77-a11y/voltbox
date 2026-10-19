import { useEffect, useMemo, useState } from 'react';
import { CURRENCY_SYMBOL } from '../../constants/index.js';
import { t } from '../../i18n/index.js';

// The two range inputs lie over one track and ignore the pointer except on their
// thumbs (18px circle, 2px primary-600 border). The global focus ring would wrap
// the whole 24px-high input, so it is moved onto the thumb.
const THUMB_CLASS = [
  'pointer-events-none absolute -top-2.5 h-6 w-full appearance-none bg-transparent focus-visible:![box-shadow:none]',
  '[&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:h-[18px] [&::-moz-range-thumb]:w-[18px] [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-solid [&::-moz-range-thumb]:border-primary-600 [&::-moz-range-thumb]:bg-surface',
  '[&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-[18px] [&::-webkit-slider-thumb]:w-[18px] [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-solid [&::-webkit-slider-thumb]:border-primary-600 [&::-webkit-slider-thumb]:bg-surface',
  '[&:focus-visible::-webkit-slider-thumb]:shadow-[0_0_0_2px_rgb(var(--c-surface)),0_0_0_4px_rgb(var(--c-primary-500))]',
  '[&:focus-visible::-moz-range-thumb]:shadow-[0_0_0_2px_rgb(var(--c-surface)),0_0_0_4px_rgb(var(--c-primary-500))]',
].join(' ');

/**
 * ფასის დიაპაზონი — ორი გადამფარავი range input + რიცხვითი ველები.
 * ცვლილება იგზავნება მხოლოდ commit-ზე (mouseup / blur), რომ URL არ „აჟრიალდეს“.
 */
export default function PriceRangeSlider({ min = 0, max = 100, value = null, onChange }) {
  const bounds = useMemo(
    () => ({ min: Math.floor(min), max: Math.max(Math.ceil(max), Math.floor(min) + 1) }),
    [min, max],
  );

  const [range, setRange] = useState(() => value || [bounds.min, bounds.max]);

  useEffect(() => {
    setRange(value || [bounds.min, bounds.max]);
  }, [value, bounds.min, bounds.max]);

  const [low, high] = range;
  const span = bounds.max - bounds.min || 1;
  const leftPercent = ((low - bounds.min) / span) * 100;
  const rightPercent = ((high - bounds.min) / span) * 100;

  function updateLow(next) {
    setRange([Math.min(Number(next), high), high]);
  }

  function updateHigh(next) {
    setRange([low, Math.max(Number(next), low)]);
  }

  function commit() {
    if (low <= bounds.min && high >= bounds.max) onChange(null);
    else onChange([low, high]);
  }

  return (
    <div className="border-b border-line py-4">
      <h3 className="font-serif text-[15px] font-medium leading-snug text-ink-900">{t('filters.price')}</h3>

      <div className="relative mt-5 h-1">
        <div className="absolute inset-0 rounded-pill bg-ink-200" />
        <div
          className="absolute h-1 rounded-pill bg-primary-600"
          style={{ left: `${leftPercent}%`, right: `${100 - rightPercent}%` }}
        />
        <input
          type="range"
          min={bounds.min}
          max={bounds.max}
          value={low}
          aria-label={t('filters.minPrice')}
          onChange={(e) => updateLow(e.target.value)}
          onMouseUp={commit}
          onTouchEnd={commit}
          onKeyUp={commit}
          className={THUMB_CLASS}
        />
        <input
          type="range"
          min={bounds.min}
          max={bounds.max}
          value={high}
          aria-label={t('filters.maxPrice')}
          onChange={(e) => updateHigh(e.target.value)}
          onMouseUp={commit}
          onTouchEnd={commit}
          onKeyUp={commit}
          className={THUMB_CLASS}
        />
      </div>

      <div className="mt-5 flex items-center gap-2">
        <label className="flex-1">
          <span className="sr-only">{t('filters.minPrice')}</span>
          <input
            type="number"
            value={low}
            min={bounds.min}
            max={high}
            onChange={(e) => updateLow(e.target.value)}
            onBlur={commit}
            className="field-text h-9 w-full rounded-control border border-ink-300 bg-surface px-2.5 tabular-nums text-ink-900 transition-colors hover:border-primary-500 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
          />
        </label>
        <span className="text-ink-400" aria-hidden="true">
          —
        </span>
        <label className="flex-1">
          <span className="sr-only">{t('filters.maxPrice')}</span>
          <input
            type="number"
            value={high}
            min={low}
            max={bounds.max}
            onChange={(e) => updateHigh(e.target.value)}
            onBlur={commit}
            className="field-text h-9 w-full rounded-control border border-ink-300 bg-surface px-2.5 tabular-nums text-ink-900 transition-colors hover:border-primary-500 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
          />
        </label>
        <span className="text-sm text-ink-500">{CURRENCY_SYMBOL}</span>
      </div>
    </div>
  );
}
