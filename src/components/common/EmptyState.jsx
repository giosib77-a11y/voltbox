import { PackageSearch } from 'lucide-react';
import Button from './Button.jsx';

/**
 * ცარიელი მდგომარეობა — ყოველთვის ქმედების ღილაკით.
 */
export default function EmptyState({
  icon: Icon = PackageSearch,
  title = 'შედეგები ვერ მოიძებნა',
  description = '',
  actionLabel = '',
  onAction = null,
  actionTo = '',
  secondaryAction = null,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-card border border-dashed border-ink-300 bg-white px-6 py-14 text-center ${className}`}
    >
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-ink-100">
        <Icon className="h-7 w-7 text-ink-500" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-semibold text-ink-900">{title}</h3>
      {description && <p className="mt-1.5 max-w-md text-sm text-ink-600">{description}</p>}

      {(actionLabel && (onAction || actionTo)) || secondaryAction ? (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          {actionLabel && (onAction || actionTo) && (
            <Button onClick={onAction || undefined} to={actionTo || undefined}>
              {actionLabel}
            </Button>
          )}
          {secondaryAction}
        </div>
      ) : null}
    </div>
  );
}
