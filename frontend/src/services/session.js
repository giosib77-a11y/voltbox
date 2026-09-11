/**
 * Session storage and single-flight access-token refresh.
 *
 * What it does: owns the persisted auth session (`auth:v1` in localStorage) and
 * knows how to exchange a refresh token for a new access token. When several
 * requests get a 401 at the same time, they all await one shared refresh call
 * instead of firing one refresh each — a burst of refreshes would rotate the
 * token repeatedly and log the user out, because the backend revokes the old
 * refresh token on every use (rotation-on-use).
 * Where it fits: used by httpApi.js `request()`; the storefront and the admin
 * panel share it, so a refresh triggered by one benefits the other.
 * Notes: this module deliberately uses a bare `fetch` for `/auth/refresh` rather
 * than importing httpApi, which would be circular.
 */

import { STORAGE_KEYS } from '../constants/index.js';
import { readJSON, writeJSON } from '../utils/storage.js';

const BASE_URL = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');

/** Paths whose own 401 must never trigger a refresh (it would recurse). */
const NO_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'];

/** The in-flight refresh, shared by every caller until it settles. */
let inFlight = null;

/**
 * Reads the persisted session, or null when there is none.
 *
 * A stored session from before the refresh token moved into a cookie is
 * discarded: its `refreshToken` is a value this client can no longer use, and
 * keeping the rest would leave the user apparently signed in with an access
 * token that expires in half an hour and nothing to renew it with. One
 * re-login at the changeover, rather than a session that dies confusingly.
 */
export function readSession() {
  const stored = readJSON(STORAGE_KEYS.auth, null);
  if (stored && 'refreshToken' in stored) {
    clearSession();
    return null;
  }
  return stored;
}

/**
 * Persists a session object as returned by login/register/refresh.
 *
 * `refreshToken` is stripped rather than trusted not to be there: a single
 * server that still returned one would otherwise put the long-lived credential
 * back into localStorage, which is the exact exposure the cookie removed.
 */
export function writeSession(session) {
  if (session && 'refreshToken' in session) {
    const { refreshToken: _ignored, ...rest } = session;
    writeJSON(STORAGE_KEYS.auth, rest);
    return;
  }
  writeJSON(STORAGE_KEYS.auth, session);
}

/** Drops the session. Called on logout and when a refresh fails. */
export function clearSession() {
  writeJSON(STORAGE_KEYS.auth, null);
}

/** Current access token, or null. */
export function getAccessToken() {
  return readSession()?.token ?? null;
}

/** True when a 401 from this path must not be retried through a refresh. */
export function isAuthPath(path) {
  return NO_REFRESH_PATHS.some((p) => path.startsWith(p));
}

/**
 * Default reaction to an unrecoverable 401: drop the session and send the user
 * to the login page that matches where they are, preserving the return path.
 */
function defaultOnSessionLost() {
  if (typeof window === 'undefined') return;
  const { pathname, search } = window.location;
  const here = `${pathname}${search}`;
  const isAdmin = pathname.startsWith('/admin');
  const target = isAdmin
    ? `/admin/login?next=${encodeURIComponent(here)}`
    : `/login?redirect=${encodeURIComponent(here)}`;
  // Already on the login page — navigating again would loop.
  if (pathname === '/admin/login' || pathname === '/login') return;
  window.location.assign(target);
}

let onSessionLost = defaultOnSessionLost;

/**
 * Overrides what happens when the session cannot be recovered.
 * Exists so the router (and tests) can react without a full page load.
 */
export function setSessionLostHandler(handler) {
  onSessionLost = typeof handler === 'function' ? handler : defaultOnSessionLost;
}

/**
 * Exchanges the refresh token for a new session, at most once concurrently.
 *
 * Returns the new access token, or null when the session is gone. Every caller
 * that arrives while a refresh is running gets the same promise.
 */
export function refreshSession() {
  if (inFlight) return inFlight;

  // No stored session means a guest, and a guest's 401 is an answer about
  // permission, not an expired token. Firing a refresh would spend a request
  // to learn nothing and would send them to the login page from, say, guest
  // checkout. The cookie itself is httpOnly and cannot be inspected here, so
  // the stored session is what tells us whether there is one to spend.
  if (!readSession()) return Promise.resolve(null);

  inFlight = (async () => {
    let response;
    try {
      // No body and no token: the refresh token is an httpOnly cookie, which
      // the browser attaches by itself. `credentials: 'include'` is what makes
      // it do so if the API is ever served from another origin; same-origin
      // sends it either way.
      response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
    } catch {
      // Network failure: the session may still be valid, so keep it and let the
      // caller surface the original error rather than logging the user out.
      return null;
    }

    if (!response.ok) {
      clearSession();
      onSessionLost();
      return null;
    }

    const session = await response.json().catch(() => null);
    if (!session?.token) {
      clearSession();
      onSessionLost();
      return null;
    }
    writeSession(session);
    return session.token;
  })().finally(() => {
    inFlight = null;
  });

  return inFlight;
}

/** Test hook: forgets any in-flight refresh and restores the default handler. */
export function __resetSessionStateForTests() {
  inFlight = null;
  onSessionLost = defaultOnSessionLost;
}
