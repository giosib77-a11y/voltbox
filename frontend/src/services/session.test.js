/**
 * What a signed-in shopper reads when the refresh behind an expired token fails
 * without ending the session.
 *
 * A refresh that got no answer at all is a connection problem and says so
 * (`apiErrors.network`); one the server answered with 429 or 5xx keeps the
 * general words. Both keep the session.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as httpApi from './httpApi.js';
import {
  __resetSessionStateForTests,
  readSession,
  refreshFailedOnNetwork,
  refreshSession,
  setSessionLostHandler,
  writeSession,
} from './session.js';
import { t } from '../i18n/index.js';

const reply = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});
const unauthorized = () => reply({ error: { code: 'INVALID_TOKEN', message: 'expired' } }, 401);

beforeEach(() => {
  __resetSessionStateForTests();
  localStorage.clear();
  setSessionLostHandler(vi.fn());
  writeSession({ user: { id: 'u1' }, token: 'expired' });
});

/**
 * Replaces the deadline signal with one the test fires by hand, and returns the
 * controller. Real timers would make the test wait 45 s; the claim under test
 * is "the refresh is given the deadline signal and gives up when it fires".
 */
function controlDeadline() {
  const controller = new AbortController();
  const spy = vi.spyOn(AbortSignal, 'timeout').mockReturnValue(controller.signal);
  return { controller, spy };
}

/** A fetch that never answers and rejects only when its signal aborts, like a real one. */
function hangingUntilAborted(init) {
  return new Promise((_, reject) => {
    init?.signal?.addEventListener('abort', () => reject(new DOMException('timeout', 'TimeoutError')));
  });
}

/** Settles to PENDING when `promise` has not settled within a short real wait. */
const PENDING = Symbol('pending');
const settleOrPending = (promise) =>
  Promise.race([promise, new Promise((resolve) => setTimeout(() => resolve(PENDING), 50))]);

describe('a refresh the server never answers', () => {
  afterEach(() => vi.restoreAllMocks());

  it('is given up at the request deadline and keeps the session', async () => {
    const { controller, spy } = controlDeadline();
    global.fetch = vi.fn((url, init) => hangingUntilAborted(init));

    const refresh = refreshSession();
    controller.abort();
    const result = await settleOrPending(refresh);

    expect(spy).toHaveBeenCalledWith(45_000);
    expect(result).toBeNull();
    expect(readSession()).not.toBeNull();
    expect(refreshFailedOnNetwork()).toBe(true);
  });

  it('keeps the session when the deadline passes while the body is being read', async () => {
    const { controller } = controlDeadline();
    global.fetch = vi.fn(async (url, init) => ({
      ok: true,
      status: 200,
      json: () => hangingUntilAborted(init),
    }));

    const refresh = refreshSession();
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalled());
    controller.abort();
    const result = await settleOrPending(refresh);

    expect(result).toBeNull();
    expect(readSession()).not.toBeNull();
    expect(refreshFailedOnNetwork()).toBe(true);
  });

  it('still ends the session when the body arrived and holds no token', async () => {
    controlDeadline();
    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError('bad json');
      },
    }));

    const result = await settleOrPending(refreshSession());

    expect(result).toBeNull();
    expect(readSession()).toBeNull();
  });

  it('shows the connection error to the request that waited on it', async () => {
    const { controller } = controlDeadline();
    global.fetch = vi.fn(async (url, init) =>
      url.endsWith('/auth/refresh') ? hangingUntilAborted(init) : unauthorized(),
    );

    const pending = httpApi.getOrders().catch((e) => e);
    await vi.waitFor(() =>
      expect(global.fetch.mock.calls.some(([url]) => url.endsWith('/auth/refresh'))).toBe(true),
    );
    controller.abort();
    const error = await settleOrPending(pending);

    expect(error.message).toBe(t('apiErrors.network'));
    expect(readSession()).not.toBeNull();
  });
});

describe('a refresh that fails but keeps the session', () => {
  it('tells the shopper the connection failed when the refresh got no answer', async () => {
    global.fetch = vi.fn(async (url) => {
      if (url.endsWith('/auth/refresh')) throw new TypeError('offline');
      return unauthorized();
    });

    const error = await httpApi.getOrders().catch((e) => e);

    expect(error.message).toBe(t('apiErrors.network'));
    expect(readSession()).not.toBeNull();
  });

  it('does not carry an earlier offline refresh into a later 503 one', async () => {
    let offline = true;
    global.fetch = vi.fn(async (url) => {
      if (url.endsWith('/auth/refresh')) {
        if (offline) throw new TypeError('offline');
        return reply({ error: { code: 'X' } }, 503);
      }
      return unauthorized();
    });

    const first = await httpApi.getOrders().catch((e) => e);
    expect(first.message).toBe(t('apiErrors.network'));

    offline = false;
    const second = await httpApi.getOrders().catch((e) => e);

    expect(second.message).toBe(t('apiErrors.fallback'));
  });

  it('keeps the general words when the server answered the refresh with a 5xx', async () => {
    global.fetch = vi.fn(async (url) =>
      url.endsWith('/auth/refresh') ? reply({ error: { code: 'X' } }, 503) : unauthorized(),
    );

    const error = await httpApi.getOrders().catch((e) => e);

    expect(error.message).toBe(t('apiErrors.fallback'));
    expect(readSession()).not.toBeNull();
  });
});
