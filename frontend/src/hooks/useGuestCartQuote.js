import { useEffect, useRef } from 'react';
import { useAuth } from './useAuth.js';
import { useCart } from './useCart.js';
import { useToast } from './useToast.js';
import { t } from '../i18n/index.js';

/**
 * Refresh a guest's basket against today's catalogue once, when the cart or
 * checkout page opens, and tell the shopper if anything moved.
 *
 * Waits for the session check (`initializing`): a signed-in shopper whose
 * session is still being restored looks like a guest for a moment, and their
 * lines come from the account, not from a quote. One message at most, whatever
 * changed - see `reconcileWithQuote` for the order of importance. A failed
 * request says nothing; the basket stays as it is and the server still prices
 * the order.
 */
export function useGuestCartQuote() {
  const { items, refreshFromQuote } = useCart();
  const { isAuthenticated, initializing } = useAuth();
  const toast = useToast();
  const askedRef = useRef(false);
  const hasItems = items.length > 0;

  useEffect(() => {
    if (askedRef.current || initializing || isAuthenticated || !hasItems) return;
    askedRef.current = true;
    refreshFromQuote().then((change) => {
      if (change) toast.info(t(`cart.quote.${change}`));
    });
  }, [initializing, isAuthenticated, hasItems, refreshFromQuote, toast]);
}
