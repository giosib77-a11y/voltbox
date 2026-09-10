/**
 * AdminDashboard: the /admin landing page.
 *
 * What it does: for now, confirms the panel is wired end to end. Phase 3
 * replaces this with the real KPI dashboard fed by GET /admin/dashboard.
 * Where it fits: the index route of the admin tree.
 */

import { useAdminSession } from '../useAdminSession.js';

export default function AdminDashboard() {
  const { admin } = useAdminSession();

  return (
    <div>
      <h1 className="text-lg font-semibold text-ink-900">მიმოხილვა</h1>
      <p className="mt-1 text-sm text-ink-600">
        მოგესალმებით{admin?.firstName ? `, ${admin.firstName}` : ''}.
      </p>
      <p className="mt-6 rounded-lg border border-dashed border-ink-300 bg-white p-6 text-sm text-ink-600">
        მაჩვენებლები, შეკვეთები და მარაგი მომდევნო ეტაპზე დაემატება.
      </p>
    </div>
  );
}
