import { NavLink, Outlet } from 'react-router-dom';
import { KeyRound, LogOut, MapPin, Package, User } from 'lucide-react';
import Breadcrumbs from '../../components/common/Breadcrumbs.jsx';
import { useAuth } from '../../hooks/useAuth.js';

/** ანგარიშის განყოფილების კარკასი — გვერდითი მენიუთი. */

const NAV = [
  { to: '/account/orders', label: 'ჩემი შეკვეთები', icon: Package },
  { to: '/account/profile', label: 'პროფილი', icon: User },
  { to: '/account/addresses', label: 'მისამართები', icon: MapPin },
  { to: '/account/password', label: 'პაროლის შეცვლა', icon: KeyRound },
];

export default function AccountLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="container-page py-5 lg:py-7">
      <Breadcrumbs items={[{ label: 'ჩემი ანგარიში' }]} className="mb-4" />

      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
          ჩემი ანგარიში
        </h1>
        <p className="mt-1 text-sm text-ink-600">
          {user?.firstName} {user?.lastName} · {user?.email}
        </p>
      </header>

      <div className="lg:flex lg:gap-7">
        <aside className="mb-5 lg:mb-0 lg:w-60 lg:shrink-0">
          <nav aria-label="ანგარიშის ნავიგაცია">
            <ul className="flex gap-2 overflow-x-auto rounded-card border border-ink-200 bg-white p-2 lg:flex-col lg:gap-1">
              {NAV.map((item) => (
                <li key={item.to} className="shrink-0 lg:shrink">
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 whitespace-nowrap rounded-control px-3 py-2.5 text-sm font-medium transition-colors ${
                        isActive
                          ? 'bg-primary-50 text-primary-700'
                          : 'text-ink-700 hover:bg-ink-100'
                      }`
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    {item.label}
                  </NavLink>
                </li>
              ))}
              <li className="shrink-0 lg:mt-1 lg:shrink lg:border-t lg:border-ink-100 lg:pt-1">
                <button
                  type="button"
                  onClick={logout}
                  className="flex w-full items-center gap-2.5 whitespace-nowrap rounded-control px-3 py-2.5 text-sm font-medium text-danger-700 transition-colors hover:bg-danger-50"
                >
                  <LogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
                  გასვლა
                </button>
              </li>
            </ul>
          </nav>
        </aside>

        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
