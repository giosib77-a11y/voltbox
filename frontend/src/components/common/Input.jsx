import { forwardRef, useId } from 'react';
import { AlertCircle } from 'lucide-react';

/**
 * ტექსტური ველი ლეიბლით, inline შეცდომითა და დახმარების ტექსტით.
 * ყოველთვის controlled — `value` და `onChange` სავალდებულოა გამომძახებელში.
 */
const Input = forwardRef(function Input(
  {
    label,
    error = '',
    hint = '',
    required = false,
    className = '',
    containerClassName = '',
    leftIcon: LeftIcon = null,
    rightSlot = null,
    id: providedId,
    ...rest
  },
  ref,
) {
  const generatedId = useId();
  const id = providedId || generatedId;
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ');

  return (
    <div className={`w-full ${containerClassName}`}>
      {label && (
        <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink-800">
          {label}
          {required && <span className="ml-0.5 text-danger-600" aria-hidden="true">*</span>}
        </label>
      )}

      <div className="relative">
        {LeftIcon && (
          <LeftIcon
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500"
            aria-hidden="true"
          />
        )}
        <input
          ref={ref}
          id={id}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          className={[
            'h-11 w-full rounded-control border bg-white px-3.5 text-sm text-ink-900 transition-colors',
            'placeholder:text-ink-500 focus:outline-none focus:ring-2 focus:ring-offset-0',
            LeftIcon ? 'pl-9' : '',
            rightSlot ? 'pr-11' : '',
            error
              ? 'border-danger-500 focus:border-danger-500 focus:ring-danger-500/30'
              : 'border-ink-300 focus:border-primary-500 focus:ring-primary-500/30',
            'disabled:bg-ink-100 disabled:text-ink-500',
            className,
          ]
            .filter(Boolean)
            .join(' ')}
          {...rest}
        />
        {rightSlot && <div className="absolute right-1.5 top-1/2 -translate-y-1/2">{rightSlot}</div>}
      </div>

      {error ? (
        <p id={errorId} className="mt-1.5 flex items-center gap-1.5 text-xs font-medium text-danger-600">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      ) : (
        hint && (
          <p id={hintId} className="mt-1.5 text-xs text-ink-500">
            {hint}
          </p>
        )
      )}
    </div>
  );
});

export default Input;
