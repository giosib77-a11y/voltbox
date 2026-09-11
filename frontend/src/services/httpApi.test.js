/**
 * Tests for the shared HTTP client's 401 handling.
 *
 * What they cover: a burst of concurrent 401s must trigger exactly one
 * `/auth/refresh` call (single-flight) and retry every original request once;
 * a failed refresh must clear the session and must not retry in a loop;
 * a 401 from an auth endpoint itself must never trigger a refresh.
 * Where it fits: guards services/session.js and the retry branch in
 * services/httpApi.js `request()`.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as httpApi from './httpApi.js';
import {
  __resetSessionStateForTests,
  readSession,
  setSessionLostHandler,
  writeSession,
} from './session.js';

/** Minimal Response stand-in — `request()` only uses ok / status / json. */
function reply(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

const unauthorized = () => reply({ error: { code: 'INVALID_TOKEN', message: 'expired' } }, 401);

beforeEach(() => {
  __resetSessionStateForTests();
  localStorage.clear();
});

describe('access token refresh', () => {
  it('refreshes once for three concurrent 401s and retries each request', async () => {
    writeSession({ user: { id: 'u1' }, token: 'old', refreshToken: 'r1' });

    const urls = [];
    global.fetch = vi.fn(async (url, options) => {
      urls.push(url);
      if (url.endsWith('/auth/refresh')) {
        return reply({ user: { id: 'u1' }, token: 'fresh', refreshToken: 'r2' });
      }
      // The stale token is rejected; the new one is accepted.
      return options.headers.Authorization === 'Bearer old' ? unauthorized() : reply({ ok: true });
    });

    const results = await Promise.all([
      httpApi.getProfile(),
      httpApi.getProfile(),
      httpApi.getProfile(),
    ]);

    const refreshes = urls.filter((u) => u.endsWith('/auth/refresh'));
    expect(refreshes).toHaveLength(1);
    expect(results).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    // 3 rejected + 1 refresh + 3 retries
    expect(urls).toHaveLength(7);
    expect(readSession().token).toBe('fresh');
  });

  it('clears the session and stops when the refresh itself fails', async () => {
    writeSession({ user: { id: 'u1' }, token: 'old', refreshToken: 'dead' });
    const lost = vi.fn();
    setSessionLostHandler(lost);

    const urls = [];
    global.fetch = vi.fn(async (url) => {
      urls.push(url);
      if (url.endsWith('/auth/refresh')) {
        return reply({ error: { code: 'INVALID_REFRESH_TOKEN', message: 'gone' } }, 401);
      }
      return unauthorized();
    });

    await expect(httpApi.getProfile()).rejects.toMatchObject({ name: 'AuthError' });

    // one attempt + one refresh, and nothing after it
    expect(urls).toEqual(['/api/v1/auth/me', '/api/v1/auth/refresh']);
    expect(readSession()).toBeNull();
    expect(lost).toHaveBeenCalledTimes(1);
  });

  it('never refreshes in response to a 401 from the login endpoint', async () => {
    const urls = [];
    global.fetch = vi.fn(async (url) => {
      urls.push(url);
      return reply({ error: { code: 'INVALID_CREDENTIALS', message: 'wrong' } }, 401);
    });

    await expect(httpApi.login({ email: 'a@b.ge', password: 'x' })).rejects.toMatchObject({
      name: 'AuthError',
    });

    expect(urls).toEqual(['/api/v1/auth/login']);
  });

  it('does not retry a second time when the refreshed token is also rejected', async () => {
    writeSession({ user: { id: 'u1' }, token: 'old', refreshToken: 'r1' });

    const urls = [];
    global.fetch = vi.fn(async (url) => {
      urls.push(url);
      if (url.endsWith('/auth/refresh')) {
        return reply({ user: { id: 'u1' }, token: 'fresh', refreshToken: 'r2' });
      }
      return unauthorized();
    });

    await expect(httpApi.getProfile()).rejects.toMatchObject({ name: 'AuthError' });

    // attempt, refresh, one retry — then stop
    expect(urls).toEqual(['/api/v1/auth/me', '/api/v1/auth/refresh', '/api/v1/auth/me']);
  });
});

describe('error envelope', () => {
  it('reads code, message and details out of the API envelope', async () => {
    global.fetch = vi.fn(async () =>
      reply(
        {
          error: {
            code: 'DUPLICATE_SKU',
            message: 'SKU already exists',
            details: [{ field: 'sku' }],
          },
        },
        409,
      ),
    );

    await expect(httpApi.getProfile()).rejects.toMatchObject({
      name: 'ConflictError',
      status: 409,
      message: 'SKU already exists',
      details: { code: 'DUPLICATE_SKU', details: [{ field: 'sku' }] },
    });
  });
});

describe('createOrder idempotency', () => {
  it('sends the key as a header and repeats it verbatim on a retry', async () => {
    const seen = [];
    global.fetch = vi.fn(async (url, options) => {
      seen.push(options.headers['Idempotency-Key']);
      if (seen.length === 1) throw new TypeError('network down');
      return reply({ orderNumber: 'VB-20260910-0001' });
    });

    const payload = {
      items: [{ productId: 'p1', qty: 2, snapshot: { price: 10 } }],
      customer: { phone: '555123456' },
      paymentMethod: 'cash',
      idempotencyKey: 'key-abc',
    };

    // First attempt fails at the network layer, the user retries with the same key.
    await expect(httpApi.createOrder(payload)).rejects.toMatchObject({ status: 0 });
    const order = await httpApi.createOrder(payload);

    expect(order.orderNumber).toBe('VB-20260910-0001');
    expect(seen).toEqual(['key-abc', 'key-abc']);
  });

  it('never puts the key in the body, which forbids unknown fields', async () => {
    global.fetch = vi.fn(async () => reply({ orderNumber: 'VB-1' }));

    await httpApi.createOrder({
      items: [{ productId: 'p1', qty: 1 }],
      customer: { phone: '555123456' },
      paymentMethod: 'cash',
      idempotencyKey: 'key-xyz',
    });

    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body).toEqual({
      items: [{ productId: 'p1', qty: 1 }],
      customer: { phone: '555123456' },
      paymentMethod: 'cash',
    });
  });
});

describe('error messages the shopper sees', () => {
  it('replaces the developer-facing rate limit text with Georgian', async () => {
    // The server message is written for a log; everything the UI is in is
    // Georgian, and "Too many requests" does not say how long to wait.
    global.fetch = vi.fn(async () =>
      reply(
        { error: { code: 'RATE_LIMITED', message: 'Too many requests. Please try again later.' } },
        429,
      ),
    );

    await expect(httpApi.getProfile()).rejects.toMatchObject({
      message: 'ძალიან ბევრი მცდელობა იყო. დაელოდეთ ერთ წუთს და სცადეთ ხელახლა.',
    });
  });

  it('keeps the server message for codes it does not know', async () => {
    global.fetch = vi.fn(async () =>
      reply({ error: { code: 'SOMETHING_NEW', message: 'a specific explanation' } }, 400),
    );

    await expect(httpApi.getProfile()).rejects.toMatchObject({
      message: 'a specific explanation',
    });
  });
});

describe('register payload', () => {
  it('sends only the fields the API accepts', async () => {
    global.fetch = vi.fn(async () => reply({ user: { id: 'u1' }, token: 't' }));

    // The form carries confirmPassword for its own validation. The API sets
    // extra=forbid, so passing it through answered 400 and registration was
    // simply broken for every visitor.
    await httpApi.register({
      firstName: 'ანა',
      lastName: 'წერეთელი',
      email: 'ana@example.ge',
      password: 'supersecret1',
      confirmPassword: 'supersecret1',
    });

    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body).toEqual({
      firstName: 'ანა',
      lastName: 'წერეთელი',
      email: 'ana@example.ge',
      password: 'supersecret1',
    });
  });
});

describe('guest order lookup', () => {
  it('sends the contact in the body, never in the URL', async () => {
    // The regression: the phone travelled as `?email=`, which wrote it into
    // every access log, proxy log and browser history entry on the way.
    localStorage.setItem('guest-orders:v1', JSON.stringify({ 'VB-20260101-0001': '555123456' }));
    const fetchMock = vi.fn().mockResolvedValue(reply({ orderNumber: 'VB-20260101-0001' }));
    vi.stubGlobal('fetch', fetchMock);

    await httpApi.getOrderByNumber('VB-20260101-0001');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/orders/lookup');
    expect(url).not.toContain('555123456');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({
      orderNumber: 'VB-20260101-0001',
      contact: '555123456',
    });
  });

  it('reads a signed-in order with a plain GET and no contact', async () => {
    localStorage.removeItem('guest-orders:v1');
    const fetchMock = vi.fn().mockResolvedValue(reply({ orderNumber: 'VB-20260101-0002' }));
    vi.stubGlobal('fetch', fetchMock);

    await httpApi.getOrderByNumber('VB-20260101-0002');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/orders/VB-20260101-0002');
    expect(init.method).toBe('GET');
  });
});

describe('the refresh token never touches JavaScript', () => {
  it('drops a session stored before the token moved into a cookie', () => {
    // Such a session holds a refreshToken this client can no longer spend.
    // Keeping the rest would look signed in for half an hour and then fail
    // with nothing to renew.
    localStorage.setItem(
      'auth:v1',
      JSON.stringify({ token: 'old-access', refreshToken: 'r1', user: { id: 'u1' } }),
    );

    expect(readSession()).toBeNull();
    expect(localStorage.getItem('auth:v1')).toBe('null');
  });

  it('refuses to persist a refresh token even if one is handed to it', () => {
    // Belt and braces: one server that still returned the field would
    // otherwise put the long-lived credential straight back in localStorage.
    writeSession({ token: 'a', refreshToken: 'should-not-be-kept', user: { id: 'u1' } });

    expect(readSession()).toEqual({ token: 'a', user: { id: 'u1' } });
    expect(localStorage.getItem('auth:v1')).not.toContain('should-not-be-kept');
  });

  it('refreshes with the cookie alone - no body, no token', async () => {
    writeSession({ token: 'expired', user: { id: 'u1' } });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(reply({ token: 'fresh', user: { id: 'u1' } }))
      .mockResolvedValueOnce(reply({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);

    await httpApi.getProfile();

    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe('/api/v1/auth/refresh');
    expect(init.body).toBeUndefined();
    expect(init.credentials).toBe('include');
  });

  it('does not refresh for a guest, who has no cookie to spend', async () => {
    localStorage.clear();
    const fetchMock = vi.fn().mockResolvedValue(unauthorized());
    vi.stubGlobal('fetch', fetchMock);

    await expect(httpApi.getProfile()).rejects.toThrow();

    // One call: the original. No refresh attempt.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
