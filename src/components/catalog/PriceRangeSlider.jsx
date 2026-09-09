import { useEffect, useMemo, useState } from 'react';
import { CURRENCY_SYMBOL } from '../../constants/index.js';

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
    <div className="border-b border-ink-200 py-4">
      <h3 className="text-sm font-semibold text-ink-900">ფასი</h3>

      <div className="relative mt-5 h-1.5">
        <div className="absolute inset-0 rounded-pill bg-ink-200" />
        <div
          className="absolute h-1.5 rounded-pill bg-primary-600"
          style={{ left: `${leftPercent}%`, right: `${100 - rightPercent}%` }}
        />
        <input
          type="range"
          min={bounds.min}
          max={bounds.max}
          value={low}
          aria-label="მინიმალური ფასი"
          onChange={(e) => updateLow(e.target.value)}
          onMouseUp={commit}
          onTouchEnd={commit}
          onKeyUp={commit}
          className="pointer-events-none absolute -top-2 h-6 w-full appearance-none bg-transparent [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-primary-600 [&::-moz-range-thumb]:bg-white [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-primary-600 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow"
        />
        <input
          type="range"
          min={bounds.min}
          max={bounds.max}
          value={high}
          aria-label="მაქსიმალური ფასი"
          onChange={(e) => updateHigh(e.target.value)}
          onMouseUp={commit}
          onTouchEnd={commit}
          onKeyUp={commit}
          className="pointer-events-none absolute -top-2 h-6 w-full appearance-none bg-transparent [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-primary-600 [&::-moz-range-thumb]:bg-white [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-primary-600 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow"
        />
      </div>

      <div className="mt-5 flex items-center gap-2">
        <label className="flex-1">
          <span className="sr-only">მინიმალური ფასი</span>
          <input
            type="number"
            value={low}
            min={bounds.min}
            max={high}
            onChange={(e) => updateLow(e.target.value)}
            onBlur={commit}
            className="h-9 w-full rounded-control border border-ink-300 px-2.5 text-sm tabular-nums focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
          />
        </label>
        <span className="text-ink-400" aria-hidden="true">
          —
        </span>
        <label className="flex-1">
          <span className="sr-only">მაქსიმალური ფასი</span>
          <input
            type="number"
            value={high}
            min={low}
            max={bounds.max}
            onChange={(e) => updateHigh(e.target.value)}
            onBlur={commit}
            className="h-9 w-full rounded-control border border-ink-300 px-2.5 text-sm tabular-nums focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
          />
        </label>
        <span className="text-sm text-ink-500">{CURRENCY_SYMBOL}</span>
      </div>
    </div>
  );
}
