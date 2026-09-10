/**
 * Tests for useIdempotencyKey.
 *
 * What they cover: the key must survive re-renders and repeated submits of the
 * same order (so a double click or a retry after a timeout replays instead of
 * creating a second order), and must change as soon as the order itself does.
 */

import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';

import { newIdempotencyKey, useIdempotencyKey } from './useIdempotencyKey.js';

const cart = (qty) => JSON.stringify({ items: [['p1', qty]], city: 'თბილისი' });

describe('useIdempotencyKey', () => {
  it('keeps the same key while the order does not change', () => {
    const { result, rerender } = renderHook(({ sig }) => useIdempotencyKey(sig), {
      initialProps: { sig: cart(1) },
    });
    const first = result.current[0];

    rerender({ sig: cart(1) });
    rerender({ sig: cart(1) });

    expect(result.current[0]).toBe(first);
    expect(first).toMatch(/^[0-9a-f-]{8,}/);
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

  it('produces distinct keys', () => {
    const keys = new Set(Array.from({ length: 50 }, newIdempotencyKey));
    expect(keys.size).toBe(50);
  });
});
