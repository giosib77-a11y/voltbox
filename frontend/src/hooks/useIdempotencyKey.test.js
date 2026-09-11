/**
 * Tests for useIdempotencyKey.
 *
 * What they cover: the key must survive re-renders and repeated submits of the
 * same order (so a double click or a retry after a timeout replays instead of
 * creating a second order), and must change as soon as the order itself does.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';

import { newIdempotencyKey, useIdempotencyKey } from './useIdempotencyKey.js';

const cart = (qty) => JSON.stringify({ items: [['p1', qty]], city: 'თბილისი' });

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

beforeEach(() => {
  sessionStorage.clear();
});

describe('useIdempotencyKey', () => {
  it('keeps the same key while the order does not change', () => {
    const { result, rerender } = renderHook(({ sig }) => useIdempotencyKey(sig), {
      initialProps: { sig: cart(1) },
    });
    const first = result.current[0];

    rerender({ sig: cart(1) });
    rerender({ sig: cart(1) });

    expect(result.current[0]).toBe(first);
    // The API refuses anything that is not a UUID.
    expect(first).toMatch(UUID_V4);
  });

  it('survives a reload of the same checkout', () => {
    // The case a ref alone could not cover: a shopper refreshes because the
    // slow request looked stuck, and the retry must replay, not re-order.
    const before = renderHook(() => useIdempotencyKey(cart(1)));
    const key = before.result.current[0];
    before.unmount();

    const after = renderHook(() => useIdempotencyKey(cart(1)));

    expect(after.result.current[0]).toBe(key);
  });

  it('does not reuse a stored key for a different order', () => {
    const first = renderHook(() => useIdempotencyKey(cart(1)));
    const key = first.result.current[0];
    first.unmount();

    // Something in the basket changed, so this is a different order - reusing
    // the key would make the server replay the previous one.
    const second = renderHook(() => useIdempotencyKey(cart(2)));

    expect(second.result.current[0]).not.toBe(key);
  });

  it('works when sessionStorage is unavailable', () => {
    // Some privacy modes throw on access rather than returning null. A
    // checkout must not fail over where its key is kept.
    const original = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage');
    Object.defineProperty(globalThis, 'sessionStorage', {
      get() {
        throw new Error('blocked');
      },
      configurable: true,
    });
    try {
      const { result, rerender } = renderHook(({ sig }) => useIdempotencyKey(sig), {
        initialProps: { sig: cart(1) },
      });
      const key = result.current[0];
      rerender({ sig: cart(1) });

      expect(key).toMatch(UUID_V4);
      expect(result.current[0]).toBe(key);
    } finally {
      Object.defineProperty(globalThis, 'sessionStorage', original);
    }
  });

  it('issues a new key when the cart changes', () => {
    const { result, rerender } = renderHook(({ sig }) => useIdempotencyKey(sig), {
      initialProps: { sig: cart(1) },
    });
    const first = result.current[0];

    rerender({ sig: cart(2) });

    expect(result.current[0]).not.toBe(first);
  });

  it('issues a new key after reset, which runs on a successful order', () => {
    const { result } = renderHook(() => useIdempotencyKey(cart(1)));
    const first = result.current[0];

    act(() => result.current[1]());

    expect(result.current[0]).not.toBe(first);
    // What is stored is the new attempt, never the finished one - an identical
    // basket ordered again must not replay the order just placed.
    const stored = JSON.parse(sessionStorage.getItem('checkout-idempotency:v1'));
    expect(stored.key).toBe(result.current[0]);
    expect(stored.key).not.toBe(first);
  });
});

describe('newIdempotencyKey', () => {
  it('falls back to getRandomValues when randomUUID is unavailable', () => {
    const original = globalThis.crypto;
    // A non-secure context (plain http on a LAN address) has no randomUUID.
    Object.defineProperty(globalThis, 'crypto', {
      value: { getRandomValues: original.getRandomValues.bind(original) },
      configurable: true,
    });
    try {
      const key = newIdempotencyKey();
      expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    } finally {
      Object.defineProperty(globalThis, 'crypto', { value: original, configurable: true });
    }
  });

  it('still produces a UUID with no crypto at all', () => {
    const original = globalThis.crypto;
    Object.defineProperty(globalThis, 'crypto', { value: undefined, configurable: true });
    try {
      expect(newIdempotencyKey()).toMatch(UUID_V4);
    } finally {
      Object.defineProperty(globalThis, 'crypto', { value: original, configurable: true });
    }
  });

  it('produces distinct keys', () => {
    const keys = new Set(Array.from({ length: 50 }, newIdempotencyKey));
    expect(keys.size).toBe(50);
  });
});
