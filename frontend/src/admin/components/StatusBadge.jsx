/**
 * StatusBadge: product and stock status.
 *
 * What it does: renders a status as text plus colour.
 * Where it fits: the products and inventory tables.
 * Notes: never colour alone. A colour-only badge is invisible to a colour-blind
 * reader and to anyone printing the page.
 */

const PRODUCT_STATUS = {
  archived: { label: 'არქივში', className: 'bg-ink-100 text-ink-700' },
  inactive: { label: 'გამორთული', className: 'bg-warning-50 text-warning-600' },
  active: { label: 'აქტიური', className: 'bg-success-50 text-success-700' },
};

const STOCK_STATUS = {
  out: { label: 'ამოწურულია', className: 'bg-danger-50 text-danger-700' },
  low: { label: 'იწურება', className: 'bg-warning-50 text-warning-600' },
  ok: { label: 'საკმარისი', className: 'bg-success-50 text-success-700' },
};

function Pill({ label, className }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}
    >
      {label}
    </span>
  );
}

/** `archived` wins over `inactive`: it is the more specific fact. */
export function productStatus(product) {
  if (product.archivedAt) return 'archived';
  return product.isActive ? 'active' : 'inactive';
}

export function ProductStatusBadge({ product }) {
  const status = PRODUCT_STATUS[productStatus(product)];
  return <Pill label={status.label} className={status.className} />;
}

export function StockBadge({ status, stock }) {
  const tone = STOCK_STATUS[status] || STOCK_STATUS.ok;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="tabular-nums text-ink-900">{stock}</span>
      {status === 'ok' ? null : <Pill label={tone.label} className={tone.className} />}
    </span>
  );
}
