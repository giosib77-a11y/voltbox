import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { LogOut, MapPin, Package, User, UserCircle2 } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth.js';

/**
 * მომხმარებლის მენიუ (desktop). არაავტორიზებულისთვის — შესვლის ბმული.
 */

const LINKS = [
  { to: '/account/orders', label: 'ჩემი შეკვეთები', icon: Package },
  { to: '/account/profile', label: 'პროფილი', icon: User },
  { to: '/account/addresses', label: 'მისამართები', icon: MapPin },
];

export default function UserMenu() {
  const { isAuthenticated, user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);

  useEffect(() => {
    function handleOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) setOpen(false);
    }
    function handleEscape(event) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, []);

  if (!isAuthenticated) {
    return (
      <Link
        to="/login"
        className="flex h-10 items-center gap-2 rounded-control px-2.5 text-sm font-medium text-ink-700 transition-colors hover:bg-ink-100 hover:text-primary-700"
      >
        <UserCircle2 className="h-5 w-5" aria-hidden="true" />
        <span className="hidden lg:inline">შესვლა</span>
      </Link>
    );
  }

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex h-10 items-center gap-2 rounded-control px-2.5 text-sm font-medium text-ink-700 transition-colors hover:bg-ink-100 hover:text-primary-700"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-100 text-xs font-bold text-primary-700">
          {(user?.firstName?.[0] || 'V').toUpperCase()}
        </span>
        <span className="hidden max-w-[7rem] truncate lg:inline">{user?.firstName}</span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-drawer mt-2 w-56 overflow-hidden rounded-card border border-ink-200 bg-white py-1.5 shadow-popover"
        >
          <div className="border-b border-ink-100 px-3 pb-2 pt-1">
            <p className="truncate text-sm font-semibold text-ink-900">
              {user?.firstName} {user?.lastName}
            </p>
            <p className="truncate text-xs text-ink-500">{user?.email}</p>
          </div>

          {LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-3 py-2 text-sm text-ink-700 transition-colors hover:bg-ink-50"
            >
              <link.icon className="h-4 w-4 text-ink-500" aria-hidden="true" />
              {link.label}
            </Link>
          ))}

          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="flex w-full items-center gap-2.5 border-t border-ink-100 px-3 py-2 text-sm text-danger-700 transition-colors hover:bg-danger-50"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            გასვლა
          </button>
        </div>
      )}
    </div>
  );
}
