/**
 * The "forgot password" link on the login page.
 *
 * It is shown only while the shop can send email - GET /delivery's
 * `features.email`. A link that leads to a form which sends nothing is worse
 * than no link: the shopper waits for an email that was never going to come.
 * Hidden too while the answer is still on its way, and when it never arrives.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

// api.js re-exports whichever implementation `.env` selects; these tests
// replace only `fetch`, so they sit on httpApi everywhere.
vi.mock('virtual:api-impl', () => import('../services/httpApi.js'));

import Login from './Login.jsx';
import { forgetDeliveryRules, loadDeliveryRules } from '../hooks/useDeliveryRules.js';
import { ToastProvider } from '../context/ToastContext.jsx';

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({ login: vi.fn(), pending: false }),
}));

const LINK = { name: 'დაგავიწყდათ პაროლი?' };

/** GET /delivery, with or without email. */
const rules = (email) => ({
  cities: [{ name: 'თბილისი', fee: '8.00' }],
  freeFrom: '50.00',
  currency: 'GEL',
  features: { email },
});

const reply = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

function renderLogin() {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Login />
      </MemoryRouter>
    </ToastProvider>,
  );
}

/** Until the rules have arrived - or failed to - and the page has redrawn. */
async function rulesSettled() {
  await act(async () => {
    await loadDeliveryRules().catch(() => {});
  });
}

beforeEach(() => {
  forgetDeliveryRules();
});

describe('the forgot-password link', () => {
  it('is hidden while the shop cannot send email', async () => {
    global.fetch = vi.fn(async () => reply(rules(false)));
    renderLogin();

    await rulesSettled();

    expect(global.fetch).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'შესვლა' })).toBeInTheDocument();
    expect(screen.queryByRole('link', LINK)).not.toBeInTheDocument();
  });

  it('is hidden when the rules cannot be loaded', async () => {
    global.fetch = vi.fn(async () => reply({}, 500));
    renderLogin();

    await rulesSettled();

    expect(global.fetch).toHaveBeenCalled();
    expect(screen.queryByRole('link', LINK)).not.toBeInTheDocument();
  });

  it('is hidden until the answer arrives', () => {
    global.fetch = vi.fn(() => new Promise(() => {}));
    renderLogin();

    expect(screen.queryByRole('link', LINK)).not.toBeInTheDocument();
  });

  it('leads to the reset form once the shop can send email', async () => {
    global.fetch = vi.fn(async () => reply(rules(true)));
    renderLogin();

    const link = await screen.findByRole('link', LINK);

    expect(link).toHaveAttribute('href', '/forgot-password');
  });
});
