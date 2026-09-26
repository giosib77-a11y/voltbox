/**
 * The form that asks for a password reset link.
 *
 * What it must not do is tell anyone whether an address has an account: the
 * server answers every address the same way, and the page says the same
 * thing after that answer whatever address was typed. Nor may it offer a
 * form while the shop cannot send the email.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

vi.mock('virtual:api-impl', () => import('../services/httpApi.js'));

import ForgotPassword from './ForgotPassword.jsx';
import { forgetDeliveryRules } from '../hooks/useDeliveryRules.js';
import { ToastProvider } from '../context/ToastContext.jsx';
import ToastViewport from '../components/common/Toast.jsx';

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
  global.fetch.mock.calls.filter(([url]) => String(url).endsWith('/auth/forgot-password'));

/** GET /delivery with email on; POST /auth/forgot-password answered by `forgot`. */
function serve({ email = true, forgot = () => reply({ ok: true }) } = {}) {
  global.fetch = vi.fn(async (url) => (isDelivery(url) ? reply(rules(email)) : forgot(url)));
}

function renderPage() {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={['/forgot-password']}>
        <ForgotPassword />
      </MemoryRouter>
      <ToastViewport />
    </ToastProvider>,
  );
}

async function ask(address) {
  fireEvent.change(await screen.findByLabelText(/^ელ\. ფოსტა/), { target: { value: address } });
  fireEvent.click(screen.getByRole('button', { name: 'ბმულის გაგზავნა' }));
}

beforeEach(() => {
  forgetDeliveryRules();
});

describe('the forgot-password form', () => {
  it('is not offered while the shop cannot send email', async () => {
    serve({ email: false });
    renderPage();

    expect(await screen.findByText(/პაროლის აღდგენა ამჟამად მიუწვდომელია/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^ელ\. ფოსტა/)).not.toBeInTheDocument();
    expect(resetRequests()).toHaveLength(0);
  });

  it('sends the address and answers without saying whether it has an account', async () => {
    serve();
    renderPage();

    await ask('  nino@example.ge ');

    const answer = await screen.findByRole('status');
    expect(answer).toHaveTextContent('თუ nino@example.ge ანგარიშს ეკუთვნის');
    const [[, options]] = resetRequests();
    expect(JSON.parse(options.body)).toEqual({ email: 'nino@example.ge' });
  });

  it('sends nothing for an address that is not one', async () => {
    serve();
    renderPage();

    await ask('nino@example');

    expect(await screen.findByText('შეიყვანეთ სწორი ელ. ფოსტა')).toBeInTheDocument();
    expect(resetRequests()).toHaveLength(0);
  });

  it('passes on the limit in words that do not name an account', async () => {
    serve({
      forgot: () =>
        reply({ error: { code: 'TOO_MANY_RESET_REQUESTS', message: 'Too many', details: null } }, 429),
    });
    renderPage();

    await ask('nino@example.ge');

    expect(
      await screen.findByText('ამ მისამართისთვის ბევრი მოთხოვნა იყო. სცადეთ ერთ საათში.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
