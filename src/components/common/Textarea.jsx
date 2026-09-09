import { forwardRef, useId } from 'react';

/** მრავალხაზიანი ველი — იმავე ვიზუალური ენით, რაც Input. */
const Textarea = forwardRef(function Textarea(
  { label, error = '', hint = '', required = false, className = '', id: providedId, rows = 4, ...rest },
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
      <textarea
        ref={ref}
        id={id}
        rows={rows}
        required={required}
        aria-invalid={error ? true : undefined}
        className={[
          'w-full rounded-control border bg-white px-3.5 py-2.5 text-sm text-ink-900 transition-colors',
          'placeholder:text-ink-500 focus:outline-none focus:ring-2',
          error
            ? 'border-danger-500 focus:border-danger-500 focus:ring-danger-500/30'
            : 'border-ink-300 focus:border-primary-500 focus:ring-primary-500/30',
          className,
        ]
          .filter(Boolean)
          .join(' ')}
        {...rest}
      />
      {error ? (
        <p className="mt-1.5 text-xs font-medium text-danger-600">{error}</p>
      ) : (
        hint && <p className="mt-1.5 text-xs text-ink-500">{hint}</p>
      )}
    </div>
  );
});

export default Textarea;
