import { ChevronLeft, ChevronRight } from 'lucide-react';

/**
 * პაგინაცია მრავალწერტილებით.
 * მიმდინარე გვერდი აღინიშნება aria-current="page"-ით.
 */

function buildPages(page, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);

  const pages = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);

  if (start > 2) pages.push('start-gap');
  for (let i = start; i <= end; i += 1) pages.push(i);
  if (end < totalPages - 1) pages.push('end-gap');
  pages.push(totalPages);

  return pages;
}

export default function Pagination({ page = 1, totalPages = 1, onChange, className = '' }) {
  if (totalPages <= 1) return null;
  const pages = buildPages(page, totalPages);

  const buttonBase =
    'flex h-10 min-w-[2.5rem] items-center justify-center rounded-control border px-2 text-sm font-semibold transition-colors';

  return (
    <nav aria-label="გვერდები" className={`flex items-center justify-center gap-1.5 ${className}`}>
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        aria-label="წინა გვერდი"
        className={`${buttonBase} border-ink-300 bg-white text-ink-700 hover:border-primary-400 hover:text-primary-700 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-ink-300 disabled:hover:text-ink-700`}
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
      </button>

      {pages.map((item) =>
        typeof item === 'string' ? (
          <span key={item} className="px-1 text-sm text-ink-400" aria-hidden="true">
            …
          </span>
        ) : (
          <button
            key={item}
            type="button"
            onClick={() => onChange(item)}
            aria-current={item === page ? 'page' : undefined}
            className={`${buttonBase} ${
              item === page
                ? 'border-primary-600 bg-primary-600 text-white'
                : 'border-ink-300 bg-white text-ink-700 hover:border-primary-400 hover:text-primary-700'
            }`}
          >
            {item}
          </button>
        ),
      )}

      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
        aria-label="შემდეგი გვერდი"
        className={`${buttonBase} border-ink-300 bg-white text-ink-700 hover:border-primary-400 hover:text-primary-700 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-ink-300 disabled:hover:text-ink-700`}
      >
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </button>
    </nav>
  );
}
