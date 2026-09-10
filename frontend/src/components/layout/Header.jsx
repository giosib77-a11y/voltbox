import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Menu, Phone, Truck } from 'lucide-react';
import Logo from './Logo.jsx';
import MobileMenu from './MobileMenu.jsx';
import UserMenu from './UserMenu.jsx';
import CartBadge from '../cart/CartBadge.jsx';
import SearchBar from '../search/SearchBar.jsx';
import { CONTACT, QUERY_KEYS, SHIPPING } from '../../constants/index.js';
import { formatPrice } from '../../utils/format.js';

/**
 * Sticky header.
 * Desktop: ლოგო · კატეგორიები · ძებნა · ანგარიში · კალათა
 * Mobile (< 768px): hamburger · ლოგო · ანგარიში/კალათა, ძებნა ცალკე ხაზში.
 */
export default function Header({ categories = [] }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  const searchDefault =
    location.pathname === '/search'
      ? new URLSearchParams(location.search).get(QUERY_KEYS.search) || ''
      : '';

  // მარშრუტის ცვლილებაზე მენიუ იხურება
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  return (
    <header className="sticky top-0 z-header border-b border-ink-200 bg-white/95 shadow-header backdrop-blur">
      {/* დამხმარე ზოლი — მხოლოდ დიდ ეკრანებზე */}
      <div className="hidden border-b border-ink-100 bg-ink-50 lg:block">
        <div className="container-page flex h-9 items-center justify-between text-xs text-ink-600">
          <p className="flex items-center gap-1.5">
            <Truck className="h-3.5 w-3.5" aria-hidden="true" />
            უფასო მიწოდება {formatPrice(SHIPPING.freeThreshold)}-ზე მეტ შეკვეთაზე
          </p>
          <a href={CONTACT.phoneHref} className="flex items-center gap-1.5 hover:text-primary-700">
            <Phone className="h-3.5 w-3.5" aria-hidden="true" />
            {CONTACT.phone}
          </a>
        </div>
      </div>

      <div className="container-page">
        <div className="flex h-16 items-center gap-3">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="მენიუს გახსნა"
            className="-ml-2 flex h-10 w-10 items-center justify-center rounded-control text-ink-700 transition-colors hover:bg-ink-100 md:hidden"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>

          <Logo />

          <div className="mx-auto hidden max-w-xl flex-1 md:block">
            <SearchBar defaultValue={searchDefault} />
          </div>

          <div className="ml-auto flex items-center gap-0.5 md:ml-0">
            <UserMenu />
            <CartBadge />
          </div>
        </div>

        {/* კატეგორიების ნავიგაცია — desktop */}
        <nav aria-label="კატეგორიები" className="hidden border-t border-ink-100 md:block">
          <ul className="flex items-center gap-1 overflow-x-auto py-1.5">
            {categories.map((category) => (
              <li key={category.id}>
                <NavLink
                  to={`/category/${category.slug}`}
                  className={({ isActive }) =>
                    `block whitespace-nowrap rounded-control px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-ink-700 hover:bg-ink-100 hover:text-primary-700'
                    }`
                  }
                >
                  {category.name}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* ძებნა — mobile */}
        <div className="pb-3 md:hidden">
          <SearchBar defaultValue={searchDefault} />
        </div>
      </div>

      <MobileMenu open={menuOpen} onClose={() => setMenuOpen(false)} categories={categories} />
    </header>
  );
}
