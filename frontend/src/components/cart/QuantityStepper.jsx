import { Minus, Plus } from 'lucide-react';
import { TEXT } from '../../constants/index.js';

/**
 * რაოდენობის მრიცხველი. `max` ყოველთვის მარაგით არის შეზღუდული.
 */

const SIZES = {
  sm: { wrap: 'h-9', button: 'h-9 w-9', input: 'w-10 text-sm' },
  md: { wrap: 'h-11', button: 'h-11 w-11', input: 'w-12 text-base' },
};

export default function QuantityStepper({
  value = 1,
  min = 1,
  max = 99,
  onChange,
  size = 'md',
  disabled = false,
  label = TEXT.quantity,
  className = '',
}) {
  const dims = SIZES[size] || SIZES.md;
  const safeMax = Math.max(min, max);

  function commit(next) {
    const clamped = Math.max(min, Math.min(safeMax, Math.round(Number(next) || min)));
    if (clamped !== value) onChange?.(clamped);
  }

  return (
    <div
      className={`inline-flex items-center overflow-hidden rounded-control border border-ink-300 bg-white ${dims.wrap} ${className}`}
    >
      <button
        type="button"
        onClick={() => commit(value - 1)}
        disabled={disabled || value <= min}
        aria-label="რაოდენობის შემცირება"
        className={`flex items-center justify-center text-ink-700 transition-colors hover:bg-ink-100 disabled:cursor-not-allowed disabled:text-ink-300 disabled:hover:bg-transparent ${dims.button}`}
      >
        <Minus className="h-4 w-4" aria-hidden="true" />
      </button>

      <input
        type="number"
        inputMode="numeric"
        value={value}
        min={min}
        max={safeMax}
        disabled={disabled}
        aria-label={label}
        onChange={(event) => commit(event.target.value)}
        className={`border-x border-ink-200 bg-white text-center font-semibold text-ink-900 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500/40 disabled:text-ink-400 ${dims.wrap} ${dims.input}`}
      />

      <button
        type="button"
        onClick={() => commit(value + 1)}
        disabled={disabled || value >= safeMax}
        aria-label="რაოდენობის გაზრდა"
        className={`flex items-center justify-center text-ink-700 transition-colors hover:bg-ink-100 disabled:cursor-not-allowed disabled:text-ink-300 disabled:hover:bg-transparent ${dims.button}`}
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
