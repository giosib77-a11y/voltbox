import { AlertTriangle, RotateCcw } from 'lucide-react';
import Button from './Button.jsx';
import { TEXT } from '../../constants/index.js';

/**
 * შეცდომის მდგომარეობა ხელახლა ცდის ღილაკით.
 * @param {{ error?: Error, onRetry?: () => void }} props
 */
export default function ErrorState({
  title = TEXT.errorTitle,
  description = TEXT.errorGeneric,
  error = null,
  onRetry = null,
  className = '',
}) {
  const message = error?.message && error.message !== 'Failed to fetch' ? error.message : description;

  return (
    <div
      role="alert"
      className={`flex flex-col items-center justify-center rounded-card border border-danger-100 bg-danger-50 px-6 py-12 text-center ${className}`}
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-danger-100">
        <AlertTriangle className="h-6 w-6 text-danger-600" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-semibold text-ink-900">{title}</h3>
      <p className="mt-1.5 max-w-md text-sm text-ink-700">{message}</p>
      {onRetry && (
        <Button variant="outline" className="mt-6" onClick={onRetry}>
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          {TEXT.retry}
        </Button>
      )}
    </div>
  );
}
