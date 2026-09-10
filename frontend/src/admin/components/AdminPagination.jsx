/**
 * AdminPagination: page controls for admin tables.
 *
 * What it does: previous/next plus a compact page indicator, and says how many
 * rows the filter matched.
 * Where it fits: under every paginated admin table.
 * Notes: page lives in the URL, so the caller passes a handler that updates the
 * query string rather than local state - the back button then works.
 */

import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function AdminPagination({ page, totalPages, total, limit, onPage }) {
  if (!total) return null;

  const first = (page - 1) * limit + 1;
  const last = Math.min(page * limit, total);

  return (
    <nav
      className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm"
      aria-label="გვერდები"
    >
      <p className="text-ink-600">
        ნაჩვენებია <strong className="font-medium text-ink-900">{first}–{last}</strong> სულ{' '}
        <strong className="font-medium text-ink-900">{total}</strong>-დან
      </p>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="flex h-9 items-center gap-1 rounded-lg border border-ink-300 px-3 text-ink-700 disabled:opacity-40 hover:bg-ink-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-500"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          წინა
        </button>
        <span className="px-2 text-ink-600" aria-current="page">
          {page} / {totalPages || 1}
        </span>
        <button
          type="button"
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages}
          className="flex h-9 items-center gap-1 rounded-lg border border-ink-300 px-3 text-ink-700 disabled:opacity-40 hover:bg-ink-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-500"
        >
          შემდეგი
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}
