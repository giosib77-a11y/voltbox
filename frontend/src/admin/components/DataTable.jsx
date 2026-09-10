/**
 * DataTable: the admin's main surface.
 *
 * What it does: renders rows from a column description, and covers the three
 * states a table is actually in - loading, empty and populated.
 * Where it fits: products, categories, brands, orders, inventory, customers.
 * Notes: the table scrolls inside its own container so a wide row never makes
 * the whole page scroll sideways.
 */

import Skeleton from '../../components/common/Skeleton.jsx';

export default function DataTable({
  columns,
  rows,
  rowKey = (row) => row.id,
  loading = false,
  empty = null,
  caption,
}) {
  if (loading) {
    return (
      <div className="rounded-xl border border-ink-200 bg-white p-4">
        <div className="space-y-2">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!rows.length) return empty;

  return (
    <div className="overflow-x-auto rounded-xl border border-ink-200 bg-white">
      <table className="w-full min-w-[52rem] text-sm">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr className="border-b border-ink-200 text-left text-xs uppercase tracking-wide text-ink-500">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-3 py-2.5 font-medium ${column.align === 'right' ? 'text-right' : ''} ${column.className || ''}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-ink-100 last:border-0 hover:bg-ink-50">
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-3 py-2.5 align-middle ${column.align === 'right' ? 'text-right' : ''} ${column.cellClassName || ''}`}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
