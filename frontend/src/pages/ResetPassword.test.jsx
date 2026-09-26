/**
 * Setting a new password from the emailed link.
 *
 * The token arrives in the URL's fragment, which no browser sends to a server.
 * The page reads it once, takes it out of the address bar, and sends it with
 * the new password; a link that is used, expired or replaced ends in a way
 * to ask for a new one - but only while the shop can send one.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';

vi.mock('virtual:api-impl', () => import('../services/httpApi.js'));

import ResetPassword from './ResetPassword.jsx';
import { forgetDeliveryRules } from '../hooks/useDeliveryRules.js';
import { ToastProvider } from '../context/ToastContext.jsx';

const TOKEN = 'k3Y-_tOkEn0123456789abcdefghijklmnopqrstuvw';

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

const isDelivery = (url) => String(url).endsWith('/delivery');
const resetRequests = () =>
  global.fetch.mock.calls.filter(([url]) => String(url).endsWith('/auth/reset-password'));

function serve({ email = true, reset = () => reply({ ok: true }) } = {}) {
  global.fetch = vi.fn(async (url) => (isDelivery(url) ? reply(rules(email)) : reset(url)));
}

function Where() {
  const { pathname, search, hash } = useLocation();
  return <output data-testid="where">{`${pathname}${search}${hash}`}</output>;
}

function renderPage(entry = `/reset-password#token=${TOKEN}`) {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/login" element={<p>შესვლის გვერდი</p>} />
        </Routes>
        <Where />
      </MemoryRouter>
    </ToastProvider>,
  );
}

function choose(password, again = password) {
  fireEvent.change(screen.getByLabelText(/^ახალი პაროლი/), { target: { value: password } });
  fireEvent.change(screen.getByLabelText(/^გაიმეორეთ/), { target: { value: again } });
  fireEvent.click(screen.getByRole('button', { name: 'პაროლის შეცვლა' }));
}

beforeEach(() => {
  forgetDeliveryRules();
});

describe('the reset page', () => {
  it('sends the token from the fragment with the new password, then asks for a sign-in', async () => {
    serve();
    renderPage();

    choose('brand-new-pass-7');

    expect(await screen.findByText('შესვლის გვერდი')).toBeInTheDocument();
    const [[, options]] = resetRequests();
    expect(JSON.parse(options.body)).toEqual({ token: TOKEN, newPassword: 'brand-new-pass-7' });
  });

  it('takes the token out of the address bar as soon as it has read it', async () => {
    serve();
    renderPage();

    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent(/^\/reset-password$/));
    // Still there to send.
    expect(screen.getByLabelText(/^ახალი პაროლი/)).toBeInTheDocument();
  });

  it('sends nothing when the two passwords differ', async () => {
    serve();
    renderPage();

    choose('brand-new-pass-7', 'brand-new-pass-8');

    expect(await screen.findByText('პაროლები არ ემთხვევა')).toBeInTheDocument();
    expect(resetRequests()).toHaveLength(0);
  });

  it('offers a new link when this one no longer works', async () => {
    serve({
      reset: () =>
        reply(
          { error: { code: 'INVALID_RESET_TOKEN', message: 'invalid', details: null } },
          400,
        ),
    });
    renderPage();

    choose('brand-new-pass-7');

    expect(await screen.findByRole('alert')).toHaveTextContent('ბმული არასწორია ან მისი ვადა ამოიწურა');
    expect(await screen.findByRole('link', { name: 'ახალი ბმულის მოთხოვნა' })).toHaveAttribute(
      'href',
      '/forgot-password',
    );
  });

  it('offers no new link while the shop cannot send one', async () => {
    serve({ email: false });
    renderPage('/reset-password');

    expect(await screen.findByRole('alert')).toHaveTextContent('ბმული არასრულია');
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(screen.queryByRole('link', { name: 'ახალი ბმულის მოთხოვნა' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^ახალი პაროლი/)).not.toBeInTheDocument();
  });

  it('marks the password field when the server finds it too common', async () => {
    serve({
      reset: () =>
        reply(
          {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Invalid request',
              details: [{ field: 'newPassword', message: 'too common', type: 'value_error' }],
            },
          },
          400,
        ),
    });
    renderPage();

    choose('sakartvelo');

    expect(await screen.findByText('ეს პაროლი ძალიან მარტივია — აირჩიეთ სხვა.')).toBeInTheDocument();
    expect(screen.getByLabelText(/^ახალი პაროლი/)).toHaveAttribute('aria-invalid', 'true');
  });
});
