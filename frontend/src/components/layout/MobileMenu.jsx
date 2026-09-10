import { Link } from 'react-router-dom';
import { LayoutDashboard, LogIn, LogOut, MapPin, Package, Phone, User } from 'lucide-react';
import Modal from '../common/Modal.jsx';
import CategoryIcon from '../common/CategoryIcon.jsx';
import { useAuth } from '../../hooks/useAuth.js';
import { CONTACT } from '../../constants/index.js';

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
    <Modal open={open} onClose={onClose} position="left" title="მენიუ">
      <nav aria-label="მთავარი ნავიგაცია" className="p-3">
        <p className="px-3 pb-2 pt-1 text-2xs font-bold uppercase tracking-wide text-ink-500">
          კატეგორიები
        </p>
        <ul className="space-y-0.5">
          {categories.map((category) => (
            <li key={category.id}>
              <Link
                to={`/category/${category.slug}`}
                onClick={onClose}
                className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:bg-primary-50 hover:text-primary-700"
              >
                <CategoryIcon name={category.icon} className="h-5 w-5 text-ink-500" />
                <span className="flex-1">{category.name}</span>
                {typeof category.productsCount === 'number' && (
                  <span className="text-xs text-ink-500">{category.productsCount}</span>
                )}
              </Link>
            </li>
          ))}
        </ul>

        <div className="my-3 border-t border-ink-200" />

        <p className="px-3 pb-2 text-2xs font-bold uppercase tracking-wide text-ink-500">ანგარიში</p>
        <ul className="space-y-0.5">
          {isAuthenticated ? (
            <>
              {/* იგივე, რაც desktop-ის მენიუში: ადმინს პანელამდე გზა უნდა ჰქონდეს */}
              {user?.isAdmin ? (
                <li>
                  <Link
                    to="/admin"
                    onClick={onClose}
                    className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-semibold text-accent-800 transition-colors hover:bg-accent-50"
                  >
                    <LayoutDashboard className="h-5 w-5" aria-hidden="true" />
                    ადმინ პანელი
                  </Link>
                </li>
              ) : null}
              <li>
                <Link
                  to="/account/orders"
                  onClick={onClose}
                  className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:bg-ink-100"
                >
                  <Package className="h-5 w-5 text-ink-500" aria-hidden="true" />
                  ჩემი შეკვეთები
                </Link>
              </li>
              <li>
                <Link
                  to="/account/profile"
                  onClick={onClose}
                  className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:bg-ink-100"
                >
                  <User className="h-5 w-5 text-ink-500" aria-hidden="true" />
                  პროფილი — {user?.firstName}
                </Link>
              </li>
              <li>
                <Link
                  to="/account/addresses"
                  onClick={onClose}
                  className="flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:bg-ink-100"
                >
                  <MapPin className="h-5 w-5 text-ink-500" aria-hidden="true" />
                  მისამართები
                </Link>
              </li>
              <li>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-danger-700 transition-colors hover:bg-danger-50"
                >
                  <LogOut className="h-5 w-5" aria-hidden="true" />
                  გასვლა
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
                შესვლა / რეგისტრაცია
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
      </nav>
    </Modal>
  );
}
