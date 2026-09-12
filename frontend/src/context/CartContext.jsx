import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react';
import { STORAGE_KEYS } from '../constants/index.js';
import { readJSON, writeJSON } from '../utils/storage.js';
import { calcTotals } from '../utils/pricing.js';
import * as api from '../services/api.js';

/**
 * How long to wait before pushing a change to the account.
 *
 * Holding `+` on a quantity is a burst of states, and every one of them is a
 * cart worth saving only if it is the last. The local cart is written
 * immediately regardless, so nothing on screen waits for this.
 */
const SAVE_DEBOUNCE_MS = 800;

/** API lines -> the shape the reducer stores. */
function fromApi(lines = []) {
  return lines.map((line) => ({
    productId: line.productId,
    qty: line.qty,
    snapshot: {
      name: line.snapshot?.name ?? '',
      slug: line.snapshot?.slug ?? '',
      image: line.snapshot?.image ?? '',
      price: Number(line.snapshot?.price) || 0,
      oldPrice: line.snapshot?.oldPrice ? Number(line.snapshot.oldPrice) : null,
      stock: Number(line.snapshot?.stock) || 0,
    },
  }));
}

/**
 * კალათა — Context + useReducer.
 *
 * ჩანაწერის ფორმა:
 *   { productId, qty, snapshot: { name, slug, image, price, oldPrice, stock } }
 *
 * `snapshot` აუცილებელია: კალათა არ უნდა გატყდეს, თუ პროდუქტი mock-ში
 * შეიცვალა ან წაიშალა. ფასი, რომელიც მომხმარებელმა დაინახა, რჩება ჩანაწერში.
 */

const CartContext = createContext(null);

const ACTIONS = {
  HYDRATE: 'HYDRATE',
  ADD: 'ADD',
  REMOVE: 'REMOVE',
  SET_QTY: 'SET_QTY',
  CLEAR: 'CLEAR',
};

const initialState = { items: [], hydrated: false };

function clampQty(qty, stock) {
  const max = Number.isFinite(stock) && stock > 0 ? stock : 99;
  return Math.max(0, Math.min(Math.round(Number(qty) || 0), max));
}

/** გატეხილი ან უცხო ფორმატის ჩანაწერების გაფილტვრა. */
function sanitize(items) {
  if (!Array.isArray(items)) return [];
  return items
    .filter((item) => item && typeof item.productId === 'string' && item.snapshot)
    .map((item) => ({
      productId: item.productId,
      qty: clampQty(item.qty, item.snapshot.stock),
      snapshot: {
        name: String(item.snapshot.name ?? ''),
        slug: String(item.snapshot.slug ?? ''),
        image: String(item.snapshot.image ?? ''),
        price: Number(item.snapshot.price) || 0,
        oldPrice: item.snapshot.oldPrice ? Number(item.snapshot.oldPrice) : null,
        stock: Number(item.snapshot.stock) || 0,
      },
    }))
    .filter((item) => item.qty > 0);
}

export function cartReducer(state, action) {
  switch (action.type) {
    case ACTIONS.HYDRATE:
      return { items: sanitize(action.payload), hydrated: true };

    case ACTIONS.ADD: {
      const { product, qty = 1 } = action.payload;
      const existing = state.items.find((item) => item.productId === product.id);

      if (existing) {
        const nextQty = clampQty(existing.qty + qty, product.stock);
        return {
          ...state,
          items: state.items.map((item) =>
            item.productId === product.id ? { ...item, qty: nextQty } : item,
          ),
        };
      }

      const nextQty = clampQty(qty, product.stock);
      if (nextQty <= 0) return state;

      return {
        ...state,
        items: [
          ...state.items,
          {
            productId: product.id,
            qty: nextQty,
            snapshot: {
              name: product.name,
              slug: product.slug,
              image: product.images?.[0] ?? '',
              price: product.price,
              oldPrice: product.oldPrice ?? null,
              stock: product.stock,
            },
          },
        ],
      };
    }

    case ACTIONS.SET_QTY: {
      const { productId, qty } = action.payload;
      const target = state.items.find((item) => item.productId === productId);
      if (!target) return state;

      const nextQty = clampQty(qty, target.snapshot.stock);
      if (nextQty === 0) {
        return { ...state, items: state.items.filter((item) => item.productId !== productId) };
      }
      return {
        ...state,
        items: state.items.map((item) =>
          item.productId === productId ? { ...item, qty: nextQty } : item,
        ),
      };
    }

    case ACTIONS.REMOVE:
      return { ...state, items: state.items.filter((item) => item.productId !== action.payload.productId) };

    case ACTIONS.CLEAR:
      return { ...state, items: [] };

    default:
      return state;
  }
}

export function CartProvider({ children }) {
  const [state, dispatch] = useReducer(cartReducer, initialState);
  const hydratedRef = useRef(false);
  // Read inside a callback that must not re-create itself on every change.
  const stateRef = useRef(state);
  stateRef.current = state;
  // Whether an account is signed in and therefore worth saving to.
  const savingRef = useRef(false);

  // ჰიდრაცია mount-ზე
  useEffect(() => {
    dispatch({ type: ACTIONS.HYDRATE, payload: readJSON(STORAGE_KEYS.cart, []) });
    hydratedRef.current = true;
  }, []);

  // სინქრონიზაცია ყოველ ცვლილებაზე (ჰიდრაციამდე არ ვწერთ, რომ არ წავშალოთ)
  useEffect(() => {
    if (!state.hydrated) return;
    writeJSON(STORAGE_KEYS.cart, state.items);
  }, [state.items, state.hydrated]);

  // სხვა tab-ში ცვლილების აღქმა
  useEffect(() => {
    function handleStorage(event) {
      if (event.key !== STORAGE_KEYS.cart) return;
      dispatch({ type: ACTIONS.HYDRATE, payload: readJSON(STORAGE_KEYS.cart, []) });
    }
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  /**
   * Sign-in: fold this browser's basket into the one saved on the account.
   *
   * Merged rather than replaced in either direction, because both can be real -
   * something added here before signing in, and something added last week on a
   * phone. Whichever direction "won" would throw the other away without asking.
   *
   * A failure is swallowed on purpose. The cart in this browser is untouched
   * either way, and an error toast about syncing is not what somebody who just
   * signed in needs to read.
   */
  const mergeWithAccount = useCallback(async () => {
    try {
      const merged = await api.mergeCart(stateRef.current.items);
      dispatch({ type: ACTIONS.HYDRATE, payload: fromApi(merged) });
      savingRef.current = true;
    } catch {
      /* the local cart stands, and nothing is pushed to an account */
    }
  }, []);

  /**
   * Sign-out: stop writing to the account, and empty the cart in this browser.
   *
   * Emptying is the point. The cart is saved on the account now, so nothing is
   * lost - and leaving it on screen would show the next person to use a shared
   * computer what the last one was about to buy.
   */
  const detachFromAccount = useCallback(() => {
    savingRef.current = false;
    dispatch({ type: ACTIONS.CLEAR });
  }, []);

  // Push local changes to the account, once signed in. Skipped before hydration
  // for the same reason the localStorage write is: an empty initial state must
  // not overwrite a real cart.
  useEffect(() => {
    if (!state.hydrated || !savingRef.current) return undefined;
    const timer = setTimeout(() => {
      api.saveCart(state.items).catch(() => {
        /* the local cart is authoritative while shopping */
      });
    }, SAVE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [state.items, state.hydrated]);

  const addItem = useCallback((product, qty = 1) => {
    dispatch({ type: ACTIONS.ADD, payload: { product, qty } });
  }, []);

  const removeItem = useCallback((productId) => {
    dispatch({ type: ACTIONS.REMOVE, payload: { productId } });
  }, []);

  const setQty = useCallback((productId, qty) => {
    dispatch({ type: ACTIONS.SET_QTY, payload: { productId, qty } });
  }, []);

  /**
   * Empty the cart, and tell the account at once rather than on the debounce.
   *
   * This is called after an order is placed and when somebody empties the cart
   * by hand, and both are followed by leaving. Waiting out the debounce means a
   * tab closed a moment later leaves the account holding items that were just
   * bought - visible on their phone as though the order never happened.
   */
  const clear = useCallback(() => {
    dispatch({ type: ACTIONS.CLEAR });
    if (savingRef.current) {
      api.clearCart().catch(() => {
        /* the debounced save below still gets a chance */
      });
    }
  }, []);

  /** წაშლილი ჩანაწერის აღდგენა — „დაბრუნება“ toast-ისთვის. */
  const restoreItem = useCallback((item) => {
    dispatch({
      type: ACTIONS.ADD,
      payload: {
        qty: item.qty,
        product: {
          id: item.productId,
          name: item.snapshot.name,
          slug: item.snapshot.slug,
          images: [item.snapshot.image],
          price: item.snapshot.price,
          oldPrice: item.snapshot.oldPrice,
          stock: item.snapshot.stock,
        },
      },
    });
  }, []);

  // Selector-ები — useMemo-თი, რომ ყოველ render-ზე არ გადაითვალოს
  const totals = useMemo(
    () =>
      calcTotals(
        state.items.map((item) => ({
          price: item.snapshot.price,
          oldPrice: item.snapshot.oldPrice,
          qty: item.qty,
        })),
      ),
    [state.items],
  );

  const quantities = useMemo(
    () => Object.fromEntries(state.items.map((item) => [item.productId, item.qty])),
    [state.items],
  );

  const value = useMemo(
    () => ({
      mergeWithAccount,
      detachFromAccount,
      items: state.items,
      hydrated: state.hydrated,
      itemsCount: totals.itemsCount,
      subtotal: totals.subtotal,
      shipping: totals.shipping,
      total: totals.total,
      savings: totals.savings,
      quantities,
      addItem,
      removeItem,
      setQty,
      clear,
      restoreItem,
    }),
    [
      state.items,
      state.hydrated,
      totals,
      quantities,
      addItem,
      removeItem,
      setQty,
      clear,
      restoreItem,
      mergeWithAccount,
      detachFromAccount,
    ],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCartContext() {
  const context = useContext(CartContext);
  if (!context) throw new Error('useCart უნდა გამოიძახოთ <CartProvider> -ის შიგნით');
  return context;
}

export { ACTIONS as CART_ACTIONS };
export default CartContext;
