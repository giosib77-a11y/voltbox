/**
 * useIdempotencyKey: a stable key for one checkout attempt.
 *
 * What it does: returns the same key for every retry of the same order - across
 * a double click, a retry after a timeout, and a page reload - and a fresh one
 * as soon as anything about the order changes. The backend stores the key on
 * `orders.idempotency_key` (unique) and replays the existing order when it sees
 * a repeat, so none of those can create two orders and charge the stock twice.
 * Where it fits: used by the Checkout page; the key travels to httpApi, which
 * sends it as the `Idempotency-Key` header.
 * Notes: the key lives in `sessionStorage`, not just in a ref. A reload in the
 * middle of a slow checkout - or a shopper who refreshes because nothing seemed
 * to happen - would otherwise arrive with a new key, which is exactly the
 * double order this mechanism exists to prevent. sessionStorage rather than
 * localStorage because the scope is this tab's checkout, not the browser.
 */

import { useCallback, useRef, useState } from 'react';

/** Bumped if the stored shape ever changes; stale entries are then ignored. */
const STORAGE_KEY = 'checkout-idempotency:v1';

/**
 * A UUID v4. The API rejects anything else, because a key is a permanent claim
 * on a row and free text would replay the first order forever.
 *
 * `randomUUID` needs a secure context, so plain http on a LAN address (phone
 * testing, a tunnel without TLS) does not have it.
 */
export function newIdempotencyKey() {
  const webCrypto = globalThis.crypto;

  if (typeof webCrypto?.randomUUID === 'function') return webCrypto.randomUUID();

  const bytes = new Uint8Array(16);
  if (typeof webCrypto?.getRandomValues === 'function') {
    webCrypto.getRandomValues(bytes);
  } else {
    // Last resort: not cryptographically strong, but the value is never a
    // secret - uniqueness within one browser tab is all it has to provide.
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }

  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant 10
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/**
 * Reads the stored attempt, or null.
 *
 * Every access is guarded: sessionStorage throws outright in some privacy
 * modes, and a checkout must not fail because of where its key is kept.
 */
function readStored() {
  try {
    const raw = globalThis.sessionStorage?.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return typeof parsed?.key === 'string' && typeof parsed?.signature === 'string'
      ? parsed
      : null;
  } catch {
    return null;
  }
}

function writeStored(signature, key) {
  try {
    globalThis.sessionStorage?.setItem(STORAGE_KEY, JSON.stringify({ signature, key }));
  } catch {
    // Storage unavailable or full. The ref below still holds the key for this
    // page's lifetime, which is the behaviour this hook had before.
  }
}

function clearStored() {
  try {
    globalThis.sessionStorage?.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * @param {string} signature stable description of the order being submitted
 * @returns {[string, () => void]} the current key and a way to force a new one
 */
export function useIdempotencyKey(signature) {
  // Derived during render on purpose: the key must already exist when the
  // submit handler runs, and an effect would leave the first submit without one.
  const keyRef = useRef(null);
  const signatureRef = useRef(null);
  const [, bump] = useState(0);

  if (keyRef.current === null || signatureRef.current !== signature) {
    // A stored key counts only for the order it was issued for. If the basket
    // or the delivery details changed, it is a different order and needs a
    // different key - otherwise the server would replay the previous one.
    const stored = readStored();
    const key = stored?.signature === signature ? stored.key : newIdempotencyKey();

    keyRef.current = key;
    signatureRef.current = signature;
    writeStored(signature, key);
  }

  /** Called once the order is placed: the next checkout is a new attempt. */
  const reset = useCallback(() => {
    keyRef.current = null;
    signatureRef.current = null;
    clearStored();
    bump((n) => n + 1);
  }, []);

  return [keyRef.current, reset];
}
