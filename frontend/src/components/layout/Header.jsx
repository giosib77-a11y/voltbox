import { useEffect, useState } from 'react';
import { useLocation } from 'react-router';
import { Menu, Phone, Truck } from 'lucide-react';
import { CategoryMenuButton } from './CategoryNav.jsx';
import Logo from './Logo.jsx';
import MobileMenu from './MobileMenu.jsx';
import UserMenu from './UserMenu.jsx';
import CartBadge from '../cart/CartBadge.jsx';
import SearchBar from '../search/SearchBar.jsx';
import ThemeToggle from './ThemeToggle.jsx';
import { CONTACT, QUERY_KEYS } from '../../constants/index.js';
import { useDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { formatPrice } from '../../utils/format.js';

/**
 * Sticky header.
 * Desktop: ლოგო · კატეგორიები · ძებნა · ანგარიში · კალათა — ყველა გვერდზე ერთნაირად,
 * მთავარზეც, სადაც იგივე სია hero-ს გვერდითაც დგას.
 * Mobile (< 768px): hamburger · ლოგო · ანგარიში/კალათა, ძებნა ცალკე ხაზში.
 */
export default function Header({ categories = [] }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  // The threshold comes from GET /delivery, the same table the checkout charges by.
  const { rules } = useDeliveryRules();

  const searchDefault =
    location.pathname === '/search'
      ? new URLSearchParams(location.search).get(QUERY_KEYS.search) || ''
      : '';

  // მარშრუტის ცვლილებაზე მენიუ იხურება
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  return (
    <header className="sticky top-0 z-header border-b border-line bg-canvas/85 backdrop-blur-xl supports-[backdrop-filter]:bg-canvas/70">
      {/* სინათლის წვრილი ხაზი header-ის ქვედა კიდეზე — მხოლოდ დეკორი */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 -bottom-px h-px bg-gradient-to-r from-transparent via-primary-500/50 to-transparent"
      />
      {/* დამხმარე ზოლი — მხოლოდ დიდ ეკრანებზე */}
      <div className="hidden border-b border-ink-100 lg:block">
        <div className="container-page flex h-9 items-center justify-between text-xs text-fg-muted">
          <p className="flex items-center gap-1.5">
            <Truck className="h-3.5 w-3.5 text-primary-700" aria-hidden="true" />
            {rules && <>უფასო მიწოდება {formatPrice(rules.freeFrom)}-ზე მეტ შეკვეთაზე</>}
          </p>
          <a href={CONTACT.phoneHref} className="flex items-center gap-1.5 transition-colors hover:text-fg">
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
            className="-ml-2 flex h-10 w-10 items-center justify-center rounded-control text-ink-700 transition-colors hover:bg-ink-100 hover:text-fg md:hidden"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>

          <Logo />

          <div className="hidden md:block">
            <CategoryMenuButton categories={categories} />
          </div>

          <div className="mx-auto hidden max-w-xl flex-1 md:block">
            <SearchBar defaultValue={searchDefault} />
          </div>

          <div className="ml-auto flex items-center gap-0.5 md:ml-0">
            <ThemeToggle />
            <UserMenu />
            <CartBadge />
          </div>
        </div>

        {/* ძებნა — mobile */}
        <div className="pb-3 md:hidden">
          <SearchBar defaultValue={searchDefault} />
        </div>
      </div>

      <MobileMenu open={menuOpen} onClose={() => setMenuOpen(false)} categories={categories} />
    </header>
  );
}
