import { NavLink, Outlet } from 'react-router';
import { KeyRound, LogOut, MapPin, Package, User } from 'lucide-react';
import Breadcrumbs from '../../components/common/Breadcrumbs.jsx';
import { useAuth } from '../../hooks/useAuth.js';
import { t } from '../../i18n/index.js';

/** ანგარიშის განყოფილების კარკასი — გვერდითი მენიუთი. */

const NAV = [
  { to: '/account/orders', labelKey: 'nav.orders', icon: Package },
  { to: '/account/profile', labelKey: 'nav.profile', icon: User },
  { to: '/account/addresses', labelKey: 'nav.addresses', icon: MapPin },
  { to: '/account/password', labelKey: 'auth.changePassword', icon: KeyRound },
];

export default function AccountLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="container-page py-5 lg:py-7">
      <Breadcrumbs items={[{ label: t('account.title') }]} className="mb-4" />

      <header className="mb-6">
        <h1 className="font-serif text-[28px] font-light leading-tight text-ink-900">
          {t('account.title')}
        </h1>
        <p className="mt-1 text-sm text-ink-600">
          {user?.firstName} {user?.lastName} · {user?.email}
        </p>
      </header>

      <div className="md:flex md:gap-7">
        <aside className="mb-5 md:mb-0 md:w-56 md:shrink-0">
          <nav aria-label={t('account.nav')}>
            <ul className="flex overflow-x-auto rounded-card border border-ink-200 bg-surface md:flex-col md:overflow-visible">
              {NAV.map((item) => (
                <li key={item.to} className="shrink-0 md:shrink">
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      `flex h-11 items-center gap-2.5 whitespace-nowrap border-b-2 focus-visible:ring-inset focus-visible:ring-offset-0 px-4 text-sm font-medium transition-colors md:border-b-0 md:border-l-2 ${
                        isActive
                          ? 'border-primary-500 bg-primary-50 text-ink-900'
                          : 'border-transparent text-ink-600 hover:bg-ink-100'
                      }`
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    {t(item.labelKey)}
                  </NavLink>
                </li>
              ))}
              <li className="shrink-0 md:shrink md:border-t md:border-ink-200">
                <button
                  type="button"
                  onClick={logout}
                  className="flex h-11 w-full items-center gap-2.5 whitespace-nowrap px-4 focus-visible:ring-inset focus-visible:ring-offset-0 text-sm font-medium text-danger-fg transition-colors hover:bg-danger-50"
                >
                  <LogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {t('nav.logout')}
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
