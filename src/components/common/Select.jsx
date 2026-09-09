import { forwardRef, useId } from 'react';
import { ChevronDown } from 'lucide-react';

/**
 * ჩამოსაშლელი სია.
 * @param {{ value:string, label:string }[]} options
 */
const Select = forwardRef(function Select(
  {
    label,
    options = [],
    error = '',
    required = false,
    placeholder = '',
    className = '',
    id: providedId,
    ...rest
  },
  ref,
) {
  const generatedId = useId();
  const id = providedId || generatedId;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink-800">
          {label}
          {required && <span className="ml-0.5 text-danger-600" aria-hidden="true">*</span>}
        </label>
      )}
      <div className="relative">
        <select
          ref={ref}
          id={id}
          required={required}
          aria-invalid={error ? true : undefined}
          className={[
            'h-11 w-full appearance-none rounded-control border bg-white pl-3.5 pr-10 text-sm text-ink-900',
            'transition-colors focus:outline-none focus:ring-2',
            error
              ? 'border-danger-500 focus:border-danger-500 focus:ring-danger-500/30'
              : 'border-ink-300 focus:border-primary-500 focus:ring-primary-500/30',
            className,
          ]
            .filter(Boolean)
            .join(' ')}
          {...rest}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500"
          aria-hidden="true"
        />
      </div>
      {error && <p className="mt-1.5 text-xs font-medium text-danger-600">{error}</p>}
    </div>
  );
});

export default Select;
