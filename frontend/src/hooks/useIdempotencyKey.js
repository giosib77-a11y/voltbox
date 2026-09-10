/**
 * useIdempotencyKey: a stable key for one checkout attempt.
 *
 * What it does: returns the same key for every retry of the same order, and a
 * fresh one as soon as anything about the order changes. The backend stores the
 * key on `orders.idempotency_key` (unique) and replays the existing order when
 * it sees a repeat, so a double click or a retry after a timeout cannot create
 * two orders and charge the stock twice.
 * Where it fits: used by the Checkout page; the key travels to httpApi, which
 * sends it as the `Idempotency-Key` header.
 * Notes: generating a new key per click would defeat the whole mechanism, which
 * is why the key is derived from a signature of the order rather than from the
 * click. The signature must therefore cover everything the server would store.
 */

import { useCallback, useRef, useState } from 'react';

/**
 * A UUID v4, with fallbacks for contexts where `crypto.randomUUID` is missing.
 *
 * `randomUUID` needs a secure context, so plain http on a LAN address (phone
 * testing, a tunnel without TLS) does not have it.
 */
export function newIdempotencyKey() {
  const webCrypto = globalThis.crypto;

  if (typeof webCrypto?.randomUUID === 'function') return webCrypto.randomUUID();

  if (typeof webCrypto?.getRandomValues === 'function') {
    const bytes = webCrypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant 10
    const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  // Last resort: not cryptographically strong, but uniqueness per browser tab is
  // all this needs — the value is never a secret.
  const rand = () => Math.random().toString(16).slice(2, 10);
  return `${Date.now().toString(16)}-${rand()}-${rand()}-${rand()}`;
}

/**
 * @param {string} signature stable description of the order being submitted
 * @returns {[string, () => void]} the current key and a way to force a new one
 */
export function useIdempotencyKey(signature) {
  // Derived during render on purpose: the key must already exist when the submit
  // handler runs, and an effect would leave the first submit without one.
  const keyRef = useRef(null);
  const signatureRef = useRef(null);
  const [, bump] = useState(0);

  if (keyRef.current === null || signatureRef.current !== signature) {
    keyRef.current = newIdempotencyKey();
    signatureRef.current = signature;
  }

  const reset = useCallback(() => {
    keyRef.current = null;
    bump((n) => n + 1);
  }, []);

  return [keyRef.current, reset];
}
