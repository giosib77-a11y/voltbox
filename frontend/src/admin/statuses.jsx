/**
 * Order status labels and tones for the admin UI.
 *
 * What it does: the Georgian label and colour for each status.
 * Where it fits: the orders table, the detail page and the dashboard.
 * Notes: the allowed transitions are deliberately NOT here. The server sends
 * `allowedTransitions` with every order, so the UI can never offer a move the
 * backend would refuse - duplicating the graph is how the two drift apart.
 */

export const ORDER_STATUSES = {
  pending: { label: 'მიღებული', className: 'bg-ink-100 text-ink-700' },
  confirmed: { label: 'დადასტურებული', className: 'bg-primary-50 text-primary-700' },
  processing: { label: 'მუშავდება', className: 'bg-warning-50 text-warning-600' },
  shipped: { label: 'გაგზავნილი', className: 'bg-accent-50 text-accent-800' },
  delivered: { label: 'მიწოდებული', className: 'bg-success-50 text-success-700' },
  cancelled: { label: 'გაუქმებული', className: 'bg-danger-50 text-danger-700' },
};

export const MOVEMENT_REASONS = {
  initial: 'საწყისი მარაგი',
  restock: 'შევსება',
  manual_adjustment: 'ხელით კორექტირება',
  order_placed: 'შეკვეთა',
  order_cancelled: 'შეკვეთის გაუქმება',
  return: 'დაბრუნება',
  correction: 'შესწორება',
};

/** Reasons an administrator may choose. The rest are written by the system. */
export const MANUAL_REASONS = ['restock', 'manual_adjustment', 'return', 'correction'];

/** These two demand an explanation, and the API refuses them without one. */
export const REASONS_NEEDING_NOTE = ['manual_adjustment', 'correction'];

export function OrderStatusBadge({ status }) {
  const tone = ORDER_STATUSES[status] || ORDER_STATUSES.pending;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tone.className}`}
    >
      {tone.label}
    </span>
  );
}
