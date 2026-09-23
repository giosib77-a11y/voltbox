/**
 * The redirect guarantee end to end: the pages that read `?redirect=` and
 * `?next=`, mounted in a real router, signing in and navigating.
 *
 * What it covers: that the value a page hands to `navigate()` is the one
 * getSafeRedirect approved - a safe path is followed, and the shapes that
 * leave the site land on the page's default instead. redirect.test.js checks
 * the function alone; this checks that the pages still call it, and that the
 * router ends up where the function said.
 * Notes: only sign-in itself is replaced (useAuth, the admin API) and the
 * toasts. The router, useSearchParams and useNavigate are the real ones.
 *
 * A page that stopped calling getSafeRedirect fails here as "still on the
 * sign-in page": since 7.18 the router itself throws "External navigation is
 * not allowed" for these payloads, the page's catch reports it as a failed
 * sign-in, and nothing navigates. That refusal is the router's fix for
 * GHSA-wrjc-x8rr-h8h6 - the second line. This test is about the first.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider, createMemoryRouter } from 'react-router';

import Login from '../pages/Login.jsx';
import AdminLogin from '../admin/pages/AdminLogin.jsx';
import * as api from '../services/api.js';
import * as adminApi from '../admin/adminApi.js';
import { __resetSessionStateForTests } from '../services/session.js';

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({ login: async () => ({}), pending: false }),
}));
vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ success: () => {}, error: () => {}, info: () => {} }),
}));

const BACKSLASH = String.fromCharCode(92);

function mount(entry) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <Login /> },
      { path: '/admin/login', element: <AdminLogin /> },
      { path: '*', element: <p>landed</p> },
    ],
    { initialEntries: [entry] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

/** Where the router is, spelled out so a wrong landing reads as one. */
function whereIs(router) {
  const { pathname, search, hash } = router.state.location;
  return `${pathname}${search}${hash}`;
}

async function signIn() {
  await userEvent.type(screen.getByLabelText(/ელ\. ფოსტა/), 'owner@voltbox.ge');
  await userEvent.type(screen.getByLabelText(/^პაროლი(?!ს)/), 'supersecret1');
  await userEvent.click(screen.getByRole('button', { name: /შესვლა/ }));
}

const PAGES = [
  { page: 'Login', entry: '/login?redirect=', fallback: '/account/orders', safe: '/cart?from=mail' },
  { page: 'AdminLogin', entry: '/admin/login?next=', fallback: '/admin', safe: '/admin/orders?status=new' },
];

// Written as they would appear in a link someone sends. The last one is the
// backslash percent-encoded: the query string decodes it to `/\evil.com`
// before the page ever sees it.
const REFUSED = ['//evil.com', `/${BACKSLASH}evil.com`, '/%5Cevil.com'];

const CASES = PAGES.flatMap(({ page, entry, fallback, safe }) => [
  { page, url: entry + safe, lands: safe },
  ...REFUSED.map((payload) => ({ page, url: entry + payload, lands: fallback })),
]);

beforeEach(() => {
  __resetSessionStateForTests();
  vi.restoreAllMocks();
  vi.spyOn(api, 'login').mockResolvedValue({});
  vi.spyOn(adminApi, 'getAdminProfile').mockResolvedValue({ id: 'u1' });
});

describe('the redirect parameter, through the real router', () => {
  it.each(CASES)('$page at $url lands on $lands', async ({ url, lands }) => {
    const router = mount(url);

    await signIn();

    await waitFor(() => expect(whereIs(router)).toBe(lands));
  });
});
