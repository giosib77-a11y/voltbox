/**
 * RequireAdmin: route guard for everything under /admin.
 *
 * What it does: resolves four states - still checking, anonymous, signed in but
 * not an admin, and admin - and renders the matching outcome.
 * Where it fits: wraps the admin routes in App.jsx.
 * Notes: this is UX only. The real authorization is require_admin on the
 * backend router; a user who edits localStorage gets a rendered shell whose
 * every request answers 403.
 */

import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAdminSession } from './useAdminSession.js';
import AdminForbidden from './pages/AdminForbidden.jsx';

export default function RequireAdmin() {
  const { status } = useAdminSession();
  const location = useLocation();

  if (status === 'checking') {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-ink-50"
        role="status"
        aria-live="polite"
      >
        <span className="sr-only">იტვირთება…</span>
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-ink-300 border-t-accent-600" />
      </div>
    );
  }

  if (status === 'anonymous') {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/admin/login?next=${encodeURIComponent(next)}`} replace />;
  }

  if (status === 'forbidden') return <AdminForbidden />;

  return <Outlet />;
}
