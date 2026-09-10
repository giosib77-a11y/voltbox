import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ShoppingCart } from 'lucide-react';
import { useCart } from '../../hooks/useCart.js';

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
      aria-label={itemsCount > 0 ? `კალათა — ${itemsCount} პროდუქტი` : 'კალათა ცარიელია'}
      className={`relative flex h-10 w-10 items-center justify-center rounded-control text-ink-700 transition-colors hover:bg-ink-100 hover:text-primary-700 ${className}`}
    >
      <ShoppingCart className="h-5 w-5" aria-hidden="true" />
      {itemsCount > 0 && (
        <span
          className={`absolute -right-0.5 -top-0.5 flex h-5 min-w-[1.25rem] items-center justify-center rounded-pill bg-accent-600 px-1 text-2xs font-bold text-white ${
            animating ? 'animate-badge-pop' : ''
          }`}
        >
          {itemsCount > 99 ? '99+' : itemsCount}
        </span>
      )}
    </Link>
  );
}
