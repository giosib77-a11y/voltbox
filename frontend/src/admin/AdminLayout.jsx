/**
 * AdminLayout: the frame around every admin page.
 *
 * What it does: sidebar navigation, a header with the signed-in admin and a
 * logout button, and an outlet for the page.
 * Where it fits: the element for the /admin route tree, inside RequireAdmin.
 * Notes: the sidebar lists only sections that exist. Dead links that 404 make a
 * work tool feel broken, so new entries are added as their pages land.
 */

import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Boxes,
  LayoutDashboard,
  LogOut,
  Package,
  ReceiptText,
  Store,
  Tags,
  Users,
  Warehouse,
} from 'lucide-react';

import * as api from '../services/api.js';
import { useAdminSession } from './useAdminSession.js';

/** Sections rendered in the sidebar. Grows as later phases add pages. */
const NAV = [
  { to: '/admin', label: 'მიმოხილვა', icon: LayoutDashboard, end: true },
  { to: '/admin/products', label: 'პროდუქტები', icon: Package },
  { to: '/admin/categories', label: 'კატეგორიები', icon: Boxes },
  { to: '/admin/brands', label: 'ბრენდები', icon: Tags },
  { to: '/admin/orders', label: 'შეკვეთები', icon: ReceiptText },
  { to: '/admin/inventory', label: 'მარაგი', icon: Warehouse },
  { to: '/admin/customers', label: 'მომხმარებლები', icon: Users },
];

export default function AdminLayout() {
  const { admin } = useAdminSession();
  const navigate = useNavigate();

  async function handleLogout() {
    try {
      await api.logout();
    } finally {
      navigate('/admin/login', { replace: true });
    }
  }

  const fullName = [admin?.firstName, admin?.lastName].filter(Boolean).join(' ');

  return (
    <div className="flex min-h-screen bg-ink-50">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-ink-200 bg-white md:flex">
        <div className="flex h-14 items-center gap-2 border-b border-ink-200 px-4">
          <Store className="h-5 w-5 text-accent-600" aria-hidden="true" />
          <span className="font-semibold text-ink-900">VoltBox</span>
          <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[11px] font-medium text-ink-600">
            ადმინი
          </span>
        </div>
        <nav className="flex-1 p-2" aria-label="ადმინის განყოფილებები">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                [
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700',
                  isActive
                    ? 'bg-accent-50 font-medium text-accent-800'
                    : 'text-ink-700 hover:bg-ink-100',
                ].join(' ')
              }
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between gap-3 border-b border-ink-200 bg-white px-4">
          <span className="truncate text-sm text-ink-600">{fullName || admin?.email}</span>
          <button
            type="button"
            onClick={handleLogout}
            className="flex items-center gap-1.5 rounded-lg border border-ink-300 px-3 py-1.5 text-sm text-ink-700 hover:bg-ink-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-500"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            გასვლა
          </button>
        </header>

        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
