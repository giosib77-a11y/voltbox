/**
 * The footer's four information links, through the app's own route table.
 *
 * What it covers: that each link under "ინფორმაცია" lands on the page of the
 * same name, at the path the link names. The links used to point at two
 * categories and the home page. A router assembled inside a test would agree
 * with any path it was given, so this renders <App /> itself - its routes,
 * its Layout, the real footer.
 * Notes: the header needs the auth and cart providers and is not what this
 * checks, so it is stubbed. App creates its router once, on import, so the
 * tests share its history: each starts on the page the previous one opened,
 * the first on a 404, and checks it is not already where it is going.
 *
 * App takes RouterProvider from `react-router/dom`, the pages take their hooks
 * from `react-router`. Under Vitest the two load as separate instances, so the
 * provider's context is not the one the hooks read ("useLocation() may be used
 * only in the context of a <Router>") - on Windows with Node 24 and on Linux
 * with Node 22 alike. The browser bundle has one instance. The mock hands App
 * the `react-router` RouterProvider, which the `/dom` one only wraps to pass
 * react-dom's flushSync; routes, Layout and footer are untouched.
 */

import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { INFO_PAGES } from '../../constants/index.js';
import { ToastProvider } from '../../context/ToastContext.jsx';
import { forgetDeliveryRules } from '../../hooks/useDeliveryRules.js';

vi.mock('virtual:api-impl', () => import('../../services/httpApi.js'));
vi.mock('../../components/layout/Header.jsx', () => ({ default: () => null }));
vi.mock('react-router/dom', async () => ({
  RouterProvider: (await import('react-router')).RouterProvider,
}));

// A page is a lazy chunk; the first import of each is transformed on demand.
// Below the test's own limit, so a page that never comes names the heading it
// was waiting for instead of reporting a timeout.
const LAZY_PAGE = 3000;

const PAGES = [INFO_PAGES.delivery, INFO_PAGES.returns, INFO_PAGES.privacy, INFO_PAGES.faq];

/** GET /delivery as the server sends it; every other request answers an empty list. */
const RULES = {
  cities: [{ name: 'თბილისი', fee: '8.00' }],
  freeFrom: '50.00',
  currency: 'GEL',
  features: { email: false },
};

const reply = (body) => ({ ok: true, status: 200, json: async () => body });

let App;

beforeAll(async () => {
  window.history.replaceState(null, '', '/not-an-info-page');
  ({ default: App } = await import('../../App.jsx'));
});

beforeEach(() => {
  forgetDeliveryRules();
  global.fetch = vi.fn(async (url) => reply(String(url).endsWith('/delivery') ? RULES : []));
  // ScrollToTop runs on every navigation; jsdom does not implement scrolling
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
});

describe('the footer information links', () => {
  it.each(PAGES)('„$title“ opens its page', async (page) => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <App />
      </ToastProvider>,
    );

    const before = await screen.findByRole('heading', { level: 1 }, { timeout: LAZY_PAGE });
    expect(before).not.toHaveTextContent(page.title);

    const footer = screen.getByRole('navigation', { name: 'ინფორმაცია' });
    await user.click(within(footer).getByRole('link', { name: page.title }));

    await screen.findByRole('heading', { level: 1, name: page.title }, { timeout: LAZY_PAGE });
    expect(window.location.pathname).toBe(page.path);
  }, 10_000);
});
