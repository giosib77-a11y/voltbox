/**
 * Tests for getSafeRedirect.
 *
 * What they cover: every shape of "looks like a path, is not one". The cases
 * that matter are the ones a reviewer would wave through - a value starting
 * with a slash that still leaves the site, and a value the browser rewrites
 * after the check has passed.
 */

import { describe, expect, it } from 'vitest';

import { getSafeRedirect } from './redirect.js';

const TAB = String.fromCharCode(9);
const NEWLINE = String.fromCharCode(10);
const NUL = String.fromCharCode(0);

describe('getSafeRedirect: allowed', () => {
  it.each([
    ['/account', '/account'],
    ['/orders/42?tab=items#top', '/orders/42?tab=items#top'],
    ['/', '/'],
    // Percent-encoding survives; it is a path on this site either way.
    ['/search?q=%E1%83%9E', '/search?q=%E1%83%9E'],
  ])('keeps %s', (input, expected) => {
    expect(getSafeRedirect(input)).toBe(expected);
  });
});

describe('getSafeRedirect: refused', () => {
  it.each([
    // Protocol-relative: a slash start that lands on another origin.
    ['//evil.com'],
    // Browsers normalise the backslash to a slash, giving the same thing.
    ['/\\evil.com'],
    ['\\/evil.com'],
    ['\\\\evil.com'],
    ['https://evil.com'],
    ['http://evil.com/path'],
    ['javascript:alert(1)'],
    ['data:text/html,<script>alert(1)</script>'],
    // The one that defeats a naive check: the browser strips the tab out of
    // the URL, so this becomes //evil.com after being approved.
    [`/${TAB}/evil.com`],
    [`/${NEWLINE}/evil.com`],
    [`/${NUL}evil.com`],
    // Not a path at all.
    ['account'],
    ['../account'],
    [''],
  ])('refuses %j', (input) => {
    expect(getSafeRedirect(input)).toBe('/');
  });

  it.each([[null], [undefined], [42], [{}], [['/account']]])('refuses %j', (input) => {
    expect(getSafeRedirect(input)).toBe('/');
  });

  it('returns the fallback it was given', () => {
    expect(getSafeRedirect('//evil.com', '/account/orders')).toBe('/account/orders');
    expect(getSafeRedirect(null, '/admin')).toBe('/admin');
  });
});

describe('the tab case, spelled out', () => {
  it('would have passed a check that only looked at the first characters', () => {
    const attack = `/${TAB}/evil.com`;

    // It starts with exactly one slash...
    expect(attack.startsWith('/')).toBe(true);
    expect(attack.startsWith('//')).toBe(false);
    // ...and the browser turns it into a protocol-relative URL anyway.
    expect(attack.replace(TAB, '')).toBe('//evil.com');

    expect(getSafeRedirect(attack)).toBe('/');
  });
});

/**
 * GHSA-wrjc-x8rr-h8h6 - react-router reads some backslash forms as a
 * protocol-relative URL inside `<Link>` and `useNavigate`, turning a value that
 * looks like a path into a navigation off the site. Versions 6.0.0 through
 * 7.17.0 are affected; this project is on 6.30.x and the only published fix is
 * the 7.x major.
 *
 * Nothing reaches `navigate()` from a query string without passing through
 * `getSafeRedirect` first - Login, Register and the admin login all call it -
 * and it returns a resolved `pathname + search + hash`, so none of the shapes
 * the advisory relies on survive it.
 *
 * That is what makes deferring the major upgrade a decision rather than a hope:
 * weaken the function and these fail.
 */
const BACKSLASH = String.fromCharCode(92);

describe('the backslash open redirect, specifically', () => {
  const PAYLOADS = [
    `/${BACKSLASH}evil.com`,
    `${BACKSLASH}/evil.com`,
    `${BACKSLASH}${BACKSLASH}evil.com`,
    `${BACKSLASH}evil.com`,
    `/${BACKSLASH}/evil.com`,
    `/${BACKSLASH}${BACKSLASH}evil.com`,
    '//evil.com',
    `/..${BACKSLASH}evil.com`,
    'https://evil.com',
    // Percent-encoded: the URL parser decodes it, so the check has to hold
    // after resolution and not only on the raw string.
    '/%5Cevil.com',
  ];

  it.each(PAYLOADS)('%j never becomes an off-site navigation', (payload) => {
    const result = getSafeRedirect(payload);
    const origin = globalThis.location.origin;

    // The property that matters is where it lands, not what it spells. Two of
    // these resolve to a path on this site that happens to be *named*
    // `evil.com` (`/..\evil.com` normalises to `/evil.com`), which is a page
    // that does not exist here - not a navigation to another origin.
    expect(new URL(result, origin).origin).toBe(origin);

    expect(result.startsWith('/')).toBe(true);
    expect(result.startsWith('//')).toBe(false);
    expect(result).not.toContain(BACKSLASH);
  });
});
