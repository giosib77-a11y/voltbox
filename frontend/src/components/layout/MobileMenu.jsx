import { useId, useState } from 'react';
import { Link } from 'react-router';
import { ChevronDown, LayoutDashboard, LogIn, LogOut, MapPin, Package, Phone, User } from 'lucide-react';
import Modal from '../common/Modal.jsx';
import LanguageSwitch from './LanguageSwitch.jsx';
import CategoryIcon from '../common/CategoryIcon.jsx';
import { useAuth } from '../../hooks/useAuth.js';
import { CONTACT } from '../../constants/index.js';
import { categoryTree } from '../../utils/categoryTree.js';
import { t } from '../../i18n/index.js';

/**
 * მობილური მენიუ — slide-in drawer კატეგორიებითა და ანგარიშის ბმულებით.
 */
export default function MobileMenu({ open, onClose, categories = [] }) {
  const { isAuthenticated, user, logout } = useAuth();

  async function handleLogout() {
    await logout();
    onClose();
  }

  return (
    <Modal open={open} onClose={onClose} position="left" title={t('nav.menu')}>
      <nav aria-label={t('nav.main')} className="p-3">
        <p className="px-3 pb-2 pt-1 text-2xs font-bold uppercase tracking-wide text-ink-500">
          {t('nav.categories')}
        </p>
        <ul className="space-y-0.5">
          {categoryTree(categories).map((category) => (
            <MobileCategoryItem key={category.id} category={category} onNavigate={onClose} />
          ))}
        </ul>

        <div className="my-3 border-t border-ink-200" />

        <p className="px-3 pb-2 text-2xs font-bold uppercase tracking-wide text-ink-500">{t('nav.account')}</p>
        <ul className="space-y-0.5">
          {isAuthenticated ? (
            <>
              {/* იგივე, რაც desktop-ის მენიუში: ადმინს პანელამდე გზა უნდა ჰქონდეს.
                  A full load, not a Link: the panel is Georgian only and
                  outside the English router (i18n/index.js). */}
              {user?.isAdmin ? (
                <li>
                  <a
                    href="/admin"
                    onClick={onClose}
                    className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-semibold text-accent-fg transition-colors hover:bg-accent-50"
                  >
                    <LayoutDashboard className="h-5 w-5" aria-hidden="true" />
                    {t('nav.admin')}
                  </a>
                </li>
              ) : null}
              <li>
                <Link
                  to="/account/orders"
                  onClick={onClose}
                  className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:bg-ink-100"
                >
                  <Package className="h-5 w-5 text-ink-500" aria-hidden="true" />
                  {t('nav.orders')}
                </Link>
              </li>
              <li>
                <Link
                  to="/account/profile"
                  onClick={onClose}
                  className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:bg-ink-100"
                >
                  <User className="h-5 w-5 text-ink-500" aria-hidden="true" />
                  {t('nav.profileOf', { name: user?.firstName })}
                </Link>
              </li>
              <li>
                <Link
                  to="/account/addresses"
                  onClick={onClose}
                  className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:bg-ink-100"
                >
                  <MapPin className="h-5 w-5 text-ink-500" aria-hidden="true" />
                  {t('nav.addresses')}
                </Link>
              </li>
              <li>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-danger-fg transition-colors hover:bg-danger-50"
                >
                  <LogOut className="h-5 w-5" aria-hidden="true" />
                  {t('nav.logout')}
                </button>
              </li>
            </>
          ) : (
            <li>
              <Link
                to="/login"
                onClick={onClose}
                className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:bg-ink-100"
              >
                <LogIn className="h-5 w-5 text-ink-500" aria-hidden="true" />
                {t('nav.loginOrRegister')}
              </Link>
            </li>
          )}
        </ul>

        <div className="my-3 border-t border-ink-200" />

        <a
          href={CONTACT.phoneHref}
          className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-700 transition-colors hover:bg-ink-100"
        >
          <Phone className="h-5 w-5 text-ink-500" aria-hidden="true" />
          {CONTACT.phone}
        </a>

        <div className="my-3 border-t border-ink-200" />

        <LanguageSwitch onNavigate={onClose} className="w-full px-3 font-medium" />
      </nav>
    </Modal>
  );
}

/**
 * ფესვი ქვეკატეგორიებით — ადგილზე იშლება, ცალკე ეკრანზე არ გადადის.
 * ხე ორ დონეზე მეტი არ არის, ამიტომ ქვემენიუს ეკრანი „უკან“ ღილაკსა და focus-ის
 * მართვას მოიტანდა ისე, რომ სივრცეს არ დაზოგავდა. სახელი გადადის, ისარი შლის —
 * ერთი შეხება ორივეს ვერ იზამს.
 */
function MobileCategoryItem({ category, onNavigate }) {
  const [expanded, setExpanded] = useState(false);
  const listId = useId();
  const hasChildren = category.children.length > 0;

  return (
    <li>
      <div className="flex items-center">
        <Link
          to={`/category/${category.slug}`}
          onClick={onNavigate}
          className="flex flex-1 items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:bg-primary-50 hover:text-primary-700"
        >
          <CategoryIcon name={category.icon} className="h-5 w-5 text-ink-500" />
          <span className="flex-1">{category.name}</span>
          {typeof category.productsCount === 'number' && (
            <span className="text-xs text-ink-500">{category.productsCount}</span>
          )}
        </Link>
        {hasChildren && (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            aria-controls={listId}
            aria-label={t('nav.subcategories', { name: category.name })}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-ink-100"
          >
            <ChevronDown
              className={`h-5 w-5 transition-transform ${expanded ? 'rotate-180' : ''}`}
              aria-hidden="true"
            />
          </button>
        )}
      </div>
      {hasChildren && expanded && (
        <ul id={listId} className="mb-1 ml-8 space-y-0.5 border-l border-ink-200 pl-2">
          {category.children.map((child) => (
            <li key={child.id}>
              <Link
                to={`/category/${child.slug}`}
                onClick={onNavigate}
                className="flex items-center rounded-control px-3 py-2 text-sm text-ink-700 transition-colors hover:bg-primary-50 hover:text-primary-700"
              >
                {child.name}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
