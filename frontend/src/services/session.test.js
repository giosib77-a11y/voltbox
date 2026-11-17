/**
 * What a signed-in shopper reads when the refresh behind an expired token fails
 * without ending the session.
 *
 * A refresh that got no answer at all is a connection problem and says so
 * (`apiErrors.network`); one the server answered with 429 or 5xx keeps the
 * general words. Both keep the session.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as httpApi from './httpApi.js';
import {
  __resetSessionStateForTests,
  readSession,
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
