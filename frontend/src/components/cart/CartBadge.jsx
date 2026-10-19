import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { ShoppingCart } from 'lucide-react';
import { useCart } from '../../hooks/useCart.js';
import { t } from '../../i18n/index.js';

/**
 * კალათის აიქონი ბეჯით. რაოდენობის ცვლილებაზე ბეჯი „ხტება“.
 */
export default function CartBadge({ className = '' }) {
  const { itemsCount } = useCart();
  const [animating, setAnimating] = useState(false);
  const previous = useRef(itemsCount);

  useEffect(() => {
    if (itemsCount > previous.current) {
      setAnimating(true);
      const timer = setTimeout(() => setAnimating(false), 450);
      previous.current = itemsCount;
      return () => clearTimeout(timer);
    }
    previous.current = itemsCount;
    return undefined;
  }, [itemsCount]);

  return (
    <Link
      to="/cart"
      aria-label={itemsCount > 0 ? t('cart.badge', { count: itemsCount }) : t('cart.badgeEmpty')}
      className={`relative flex h-11 w-11 items-center justify-center rounded-pill bg-primary-600 text-on-primary transition-colors hover:bg-primary-hover active:bg-primary-press md:h-[46px] md:w-[46px] ${className}`}
    >
      <ShoppingCart className="h-[18px] w-[18px]" aria-hidden="true" />
      {itemsCount > 0 && (
        <span
          className={`absolute -right-0.5 -top-0.5 flex h-5 min-w-[1.25rem] items-center justify-center rounded-pill bg-accent-600 px-1 text-2xs font-bold text-white ring-2 ring-surface ${
            animating ? 'animate-badge-pop' : ''
          }`}
        >
          {itemsCount > 99 ? '99+' : itemsCount}
        </span>
      )}
    </Link>
  );
}
