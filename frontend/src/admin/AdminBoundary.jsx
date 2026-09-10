/**
 * AdminBoundary: the Suspense boundary for the lazy admin tree.
 *
 * What it does: provides the fallback while an admin chunk downloads.
 * Where it fits: the element of the /admin route, above RequireAdmin.
 * Notes: the storefront's boundary lives in components/layout/Layout.jsx, which
 * the admin deliberately does not use - it would bring the shop header and
 * footer with it. Without a boundary of its own, the first lazy admin chunk
 * would suspend with no ancestor to catch it.
 */

import { Suspense } from 'react';
import { Outlet } from 'react-router-dom';

export default function AdminBoundary() {
  return (
    <Suspense
      fallback={
        <div
          className="flex min-h-screen items-center justify-center bg-ink-50"
          role="status"
          aria-live="polite"
        >
          <span className="sr-only">იტვირთება…</span>
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-ink-300 border-t-accent-600" />
        </div>
      }
    >
      <Outlet />
    </Suspense>
  );
}
