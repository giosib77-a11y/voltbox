import { useEffect, useRef } from 'react';

import { useAuth } from '../hooks/useAuth.js';
import { useCart } from '../hooks/useCart.js';
import { useToast } from '../hooks/useToast.js';
import { t } from '../i18n/index.js';

/**
 * Ties the cart to whoever is signed in.
 *
 * What it does: merges this browser's basket into the account's saved one when
 * somebody signs in; on a page load with the session already there, shows the
 * account's cart instead (merging first only if this browser holds a change the
 * account has not confirmed); and empties the local one when they sign out - unless the
 * account never confirmed it holds the basket, in which case the basket stays
 * and the shopper is told it did.
 * Where it fits: rendered once at the composition root, inside both providers.
 *
 * Why a component and not a line in CartProvider: the cart must not depend on
 * auth. It works perfectly well for a guest, it is rendered on its own in
 * tests, and making the provider reach for a session would mean it could no
 * longer be used without one. The same argument puts the message here: the
 * provider would otherwise need a ToastProvider above it to render at all.
 *
 * Why loads differ from sign-ins: a merge only adds, so merging on every load
 * brings back lines bought or removed on another device. The basket kept in
 * localStorage is stale by then; the account is the newer copy.
 *
 * Keyed on the user id rather than on the object. The user is re-read on a
 * refresh and after a profile edit, and neither of those is a sign-in - merging
 * again each time would be a request per refresh for nothing.
 */
export default function CartAccountSync() {
  const { user, initializing } = useAuth();
  const { mergeWithAccount, restoreFromAccount, detachFromAccount } = useCart();
  const toast = useToast();
  const lastUserId = useRef(null);
  // Whether auth has finished once already: a user present on that first pass
  // was restored from a session, a user appearing later signed in.
  const settled = useRef(false);

  useEffect(() => {
    // Nothing is known yet; acting on "no user" here would clear a real cart
    // on every page load.
    if (initializing) return;

    const id = user?.id ?? null;
    // Before the unchanged-user bail-out: a guest's first pass counts too, so
    // a user who appears afterwards is a sign-in, not a restored session.
    const restored = !settled.current;
    settled.current = true;
    if (id === lastUserId.current) return;

    const signedOut = lastUserId.current !== null && id === null;
    lastUserId.current = id;

    if (id) {
      if (restored) restoreFromAccount();
      else mergeWithAccount();
    } else if (signedOut && detachFromAccount()) {
      // Kept, because nothing confirmed the account has it. Worth a line: the
      // basket is still on screen after signing out, which otherwise reads as
      // a bug, and it is no longer waiting on another device.
      toast.info(t('cart.keptInBrowser'));
    }
  }, [user, initializing, mergeWithAccount, restoreFromAccount, detachFromAccount, toast]);

  return null;
}
