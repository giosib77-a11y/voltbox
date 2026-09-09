import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, Home } from 'lucide-react';

/**
 * ნავიგაციის ბილიკი.
 * @param {{ items: { label: string, to?: string }[] }} props
 */
export default function Breadcrumbs({ items = [], className = '' }) {
  return (
    <nav aria-label="ნავიგაციის ბილიკი" className={`text-sm ${className}`}>
      <ol className="flex flex-wrap items-center gap-1 text-ink-500">
        <li className="flex items-center gap-1">
          <Link
            to="/"
            className="flex items-center gap-1 rounded-sm transition-colors hover:text-primary-700"
          >
            <Home className="h-3.5 w-3.5" aria-hidden="true" />
            <span>მთავარი</span>
          </Link>
        </li>

        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <Fragment key={`${item.label}-${index}`}>
              <li aria-hidden="true" className="flex items-center">
                <ChevronLeft className="h-3.5 w-3.5 text-ink-400" />
              </li>
              <li>
                {item.to && !isLast ? (
                  <Link to={item.to} className="rounded-sm transition-colors hover:text-primary-700">
                    {item.label}
                  </Link>
                ) : (
                  <span className="font-medium text-ink-800" aria-current={isLast ? 'page' : undefined}>
                    {item.label}
                  </span>
                )}
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
