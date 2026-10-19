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
import LanguageSwitch from './LanguageSwitch.jsx';
import { CONTACT, QUERY_KEYS } from '../../constants/index.js';
import { useDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { formatPrice } from '../../utils/format.js';
import { t } from '../../i18n/index.js';

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
    <header className="sticky top-0 z-header border-b border-line bg-surface">
      {/* დამხმარე ზოლი — მხოლოდ დიდ ეკრანებზე */}
      <div className="hidden border-b border-line bg-canvas lg:block">
        <div className="container-page flex items-center justify-between py-2.5 text-xs tracking-[0.04em] text-fg-muted">
          <p className="flex items-center gap-2.5">
            <Truck className="h-[15px] w-[15px] text-primary-500" aria-hidden="true" />
            {rules && t('header.freeDelivery', { price: formatPrice(rules.freeFrom) })}
          </p>
          <a
            href={CONTACT.phoneHref}
            className="flex items-center gap-2.5 transition-colors hover:text-primary-700"
          >
            <Phone className="h-3.5 w-3.5 text-primary-500" aria-hidden="true" />
            {CONTACT.phone}
          </a>
        </div>
      </div>

      <div className="container-page">
        <div className="flex h-16 items-center gap-1 md:h-auto md:gap-5 md:py-3.5">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label={t('header.openMenu')}
            className="-ml-2 flex h-11 w-11 items-center justify-center rounded-control text-ink-700 transition-colors hover:bg-ink-100 hover:text-fg active:bg-ink-200 md:hidden"
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

          <div className="ml-auto flex items-center gap-1 md:ml-0">
            {/* On a phone the switch is in the menu: the bar has no room for it. */}
            <LanguageSwitch className="hidden md:flex" />
            <ThemeToggle />
            <UserMenu />
            <CartBadge />
          </div>
        </div>

        {/* ძებნა — mobile */}
        <div className="pb-2.5 md:hidden">
          <SearchBar defaultValue={searchDefault} />
        </div>
      </div>

      <MobileMenu open={menuOpen} onClose={() => setMenuOpen(false)} categories={categories} />
    </header>
  );
}
