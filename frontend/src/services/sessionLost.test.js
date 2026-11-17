/**
 * Tests for what a dead session does, depending on who noticed it.
 *
 * What they cover: a background request (the signed-in cart sync, which runs on
 * every page load) must not send the shopper to the login page when the session
 * cannot be recovered - it only ends the session; a request the shopper asked
 * for still redirects, once, even when it shares a failed refresh with a
 * background one; and whoever is listening is told the session ended.
 * Where it fits: guards session.js `refreshSession` and the 401 branch of
 * httpClient.js `request()`.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as httpApi from './httpApi.js';
import {
  __resetSessionStateForTests,
  readSession,
  setSessionLostHandler,
  subscribeSessionEnded,
  writeSession,
} from './session.js';

function reply(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

const unauthorized = () => reply({ error: { code: 'INVALID_TOKEN', message: 'expired' } }, 401);

/** Every request is refused, and so is the refresh: the session is really gone. */
function deadSession() {
  writeSession({ user: { id: 'u1' }, token: 'expired' });
  global.fetch = vi.fn(async (url) =>
    url.endsWith('/auth/refresh') ? reply({ error: { code: 'INVALID_REFRESH_TOKEN' } }, 401) : unauthorized(),
  );
}

let lost;
beforeEach(() => {
  __resetSessionStateForTests();
  localStorage.clear();
  lost = vi.fn();
  setSessionLostHandler(lost);
});

describe('a session that cannot be recovered', () => {
  it('does not redirect when a background cart call hit it, but clears the session and says so', async () => {
    deadSession();
    const ended = vi.fn();
    subscribeSessionEnded(ended);

    await expect(httpApi.getCart()).rejects.toMatchObject({ name: 'SessionExpiredError' });

    expect(lost).not.toHaveBeenCalled();
    expect(readSession()).toBeNull();
    expect(ended).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['saveCart', () => httpApi.saveCart([])],
    ['mergeCart', () => httpApi.mergeCart([])],
    ['clearCart', () => httpApi.clearCart()],
  ])('treats %s as background too', async (_name, call) => {
    deadSession();
    await expect(call()).rejects.toMatchObject({ name: 'SessionExpiredError' });
    expect(lost).not.toHaveBeenCalled();
    expect(readSession()).toBeNull();
  });

  it('redirects when a request the shopper made hit it', async () => {
    deadSession();

    await expect(httpApi.getOrders()).rejects.toMatchObject({ name: 'SessionExpiredError' });

    expect(lost).toHaveBeenCalledTimes(1);
    expect(readSession()).toBeNull();
  });

  it('still redirects, once, when a background and a foreground request share one failed refresh', async () => {
    deadSession();

    const outcomes = await Promise.allSettled([
      httpApi.getCart(),
      httpApi.getOrders(),
      httpApi.getOrders(),
    ]);

    expect(outcomes.every((o) => o.status === 'rejected')).toBe(true);
    expect(global.fetch.mock.calls.filter(([u]) => u.endsWith('/auth/refresh'))).toHaveLength(1);
    expect(lost).toHaveBeenCalledTimes(1);
  });

  it('does not tell listeners about a refresh that failed only because the network did', async () => {
    writeSession({ user: { id: 'u1' }, token: 'expired' });
    const ended = vi.fn();
    subscribeSessionEnded(ended);
    global.fetch = vi.fn(async (url) => {
      if (url.endsWith('/auth/refresh')) throw new TypeError('offline');
      return unauthorized();
    });

    await expect(httpApi.getOrders()).rejects.toBeTruthy();

    expect(ended).not.toHaveBeenCalled();
    expect(lost).not.toHaveBeenCalled();
    expect(readSession()).not.toBeNull();
  });

  it.each([429, 500, 502, 503])(
    'keeps the session and does not redirect when the refresh answers %i',
    async (status) => {
      writeSession({ user: { id: 'u1' }, token: 'expired' });
      const ended = vi.fn();
      subscribeSessionEnded(ended);
      global.fetch = vi.fn(async (url) =>
        url.endsWith('/auth/refresh') ? reply({ error: { code: 'X' } }, status) : unauthorized(),
      );

      const error = await httpApi.getOrders().catch((e) => e);

      // httpClient.js throws `new ApiError(fallback, 0)` here. The admin shell
      // shows its "unreachable" screen only for a non-401 error, so a 401
      // (or a SessionExpiredError) would send the admin to login on an outage.
      expect(error).toMatchObject({ name: 'ApiError', status: 0 });
      expect(readSession()).toMatchObject({ token: 'expired' });
      expect(lost).not.toHaveBeenCalled();
      expect(ended).not.toHaveBeenCalled();
    },
  );

  it('recovers on the next request once the refresh endpoint answers again', async () => {
    writeSession({ user: { id: 'u1' }, token: 'expired' });
    let outage = true;
    global.fetch = vi.fn(async (url, init) => {
      if (url.endsWith('/auth/refresh')) {
        return outage ? reply({}, 503) : reply({ user: { id: 'u1' }, token: 'fresh' });
      }
      return init?.headers?.Authorization === 'Bearer fresh' ? reply([]) : unauthorized();
    });

    await expect(httpApi.getOrders()).rejects.toBeTruthy();
    expect(readSession()).not.toBeNull();

    outage = false;
    await expect(httpApi.getOrders()).resolves.toEqual([]);
    expect(readSession()).toMatchObject({ token: 'fresh' });
    expect(lost).not.toHaveBeenCalled();
  });
});
