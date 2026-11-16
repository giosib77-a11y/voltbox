/**
 * The registration form's password field.
 *
 * The browser checks only the length. A password the server refuses (a common
 * one, a repetition or sequence) has to show its reason at the field, as the
 * reset page does, not only in a generic toast.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';

vi.mock('virtual:api-impl', () => import('../services/httpApi.js'));

const register = vi.fn();
vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({ register, pending: false }),
}));

import Register from './Register.jsx';
import { ToastProvider } from '../context/ToastContext.jsx';
import ToastViewport from '../components/common/Toast.jsx';
import { ConflictError, ValidationError } from '../services/errors.js';
import { t } from '../i18n/index.js';

const refusal = (message) =>
  new ValidationError(
    t('errors.invalid'),
    {
      code: 'VALIDATION_ERROR',
      details: [{ field: 'password', message: `Value error, ${message}`, type: 'value_error' }],
    },
    400,
  );

// The input only: the show-password button's label starts with the same word.
const passwordField = () =>
  screen.getByLabelText(new RegExp('^' + t('fields.password')), { selector: 'input' });

async function submit(password) {
  const user = userEvent.setup();
  render(
    <ToastProvider>
      <MemoryRouter initialEntries={['/register']}>
        <Register />
      </MemoryRouter>
    </ToastProvider>,
  );
  await user.type(screen.getByLabelText(t('fields.firstName'), { exact: false }), 'Nino');
  await user.type(screen.getByLabelText(t('fields.lastName'), { exact: false }), 'Beridze');
  await user.type(screen.getByLabelText(t('fields.email'), { exact: false }), 'nino@example.ge');
  await user.type(passwordField(), password);
  await user.type(screen.getByLabelText(t('fields.repeatPassword'), { exact: false }), password);
  await user.click(screen.getByRole('button', { name: t('auth.createAccount') }));
}

beforeEach(() => {
  register.mockReset();
});

describe('a password the server refuses at registration', () => {
  it.each([
    ['a common one', 'This password is too common', 'auth.tooCommon'],
    ['a repetition or sequence', 'This password is a repetition or a simple sequence', 'auth.tooPatterned'],
  ])('shows the reason at the password field for %s', async (_name, message, key) => {
    register.mockRejectedValue(refusal(message));

    await submit('sakartvelo');

    expect(await screen.findByText(t(key))).toBeInTheDocument();
    await waitFor(() =>
      expect(passwordField()).toHaveAttribute('aria-invalid', 'true'),
    );
  });

  it('shows a taken email at the email field, as the real API sends it', async () => {
    register.mockRejectedValue(
      new ConflictError(t('apiErrors.EMAIL_ALREADY_EXISTS'), { code: 'EMAIL_ALREADY_EXISTS', details: null }),
    );

    await submit('sakartvelo');

    const email = screen.getByLabelText(t('fields.email'), { exact: false });
    await waitFor(() => expect(email).toHaveAttribute('aria-invalid', 'true'));
    expect(document.getElementById(email.getAttribute('aria-describedby'))).toHaveTextContent(
      t('apiErrors.EMAIL_ALREADY_EXISTS'),
    );
  });

  it('says in the hint that repetitions and sequences are not allowed', () => {
    render(
      <ToastProvider>
        <MemoryRouter initialEntries={['/register']}>
          <Register />
        </MemoryRouter>
      </ToastProvider>,
    );
    expect(screen.getByText(/გამეორება და მიმდევრობა არ შეიძლება/)).toBeInTheDocument();
  });
});

/* -------------------------------------------------------------------------- */
/* Validation, redirect and a refusal that belongs to no field                 */
/* -------------------------------------------------------------------------- */

function Where() {
  const { pathname, search } = useLocation();
  return <p data-testid="where">{`${pathname}${search}`}</p>;
}

function renderAt(url) {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[url]}>
        <Where />
        <Routes>
          <Route path="/register" element={<Register />} />
          <Route path="*" element={<p>elsewhere</p>} />
        </Routes>
      </MemoryRouter>
      <ToastViewport />
    </ToastProvider>,
  );
}

const field = (key) => screen.getByLabelText(t(key), { exact: false, selector: 'input' });
const submitButton = () => screen.getByRole('button', { name: t('auth.createAccount') });

async function fill(user, { password = 'sakartvelo', confirm = password } = {}) {
  await user.type(field('fields.firstName'), 'Nino');
  await user.type(field('fields.lastName'), 'Beridze');
  await user.type(field('fields.email'), 'nino@example.ge');
  await user.type(passwordField(), password);
  if (confirm) await user.type(field('fields.repeatPassword'), confirm);
}

describe('client-side validation', () => {
  it('shows a message at every empty field and does not call the API', async () => {
    const user = userEvent.setup();
    renderAt('/register');

    await user.click(submitButton());

    expect(register).not.toHaveBeenCalled();
    expect(screen.getByText(t('validation.firstName'))).toBeInTheDocument();
    expect(screen.getByText(t('validation.lastName'))).toBeInTheDocument();
    // email, password and the repeat all say "required"
    expect(screen.getAllByText(t('validation.required'))).toHaveLength(3);
    expect(field('fields.firstName')).toHaveAttribute('aria-invalid', 'true');
  });

  it('refuses a malformed email', async () => {
    const user = userEvent.setup();
    renderAt('/register');
    await fill(user);
    await user.clear(field('fields.email'));
    await user.type(field('fields.email'), 'not-an-email');

    await user.click(submitButton());

    expect(register).not.toHaveBeenCalled();
    expect(screen.getByText(t('validation.email'))).toBeInTheDocument();
  });

  it('refuses a password shorter than the minimum', async () => {
    const user = userEvent.setup();
    renderAt('/register');
    await fill(user, { password: 'short' });

    await user.click(submitButton());

    expect(register).not.toHaveBeenCalled();
    expect(screen.getByText(t('validation.password', { count: 8 }))).toBeInTheDocument();
  });

  it('refuses a repeat that differs from the password', async () => {
    const user = userEvent.setup();
    renderAt('/register');
    await fill(user, { password: 'sakartvelo', confirm: 'sakartvelO' });

    await user.click(submitButton());

    expect(register).not.toHaveBeenCalled();
    expect(screen.getByText(t('validation.passwordMismatch'))).toBeInTheDocument();
  });

  it('clears the mismatch once the password is changed to match', async () => {
    const user = userEvent.setup();
    renderAt('/register');
    await fill(user, { password: 'sakartvelo', confirm: 'sakartvelO' });
    await user.click(submitButton());
    expect(screen.getByText(t('validation.passwordMismatch'))).toBeInTheDocument();

    await user.clear(passwordField());
    await user.type(passwordField(), 'sakartvelO');

    expect(screen.queryByText(t('validation.passwordMismatch'))).not.toBeInTheDocument();
  });
});

describe('a successful registration', () => {
  it('sends the form values, says so, and goes to the orders page by default', async () => {
    register.mockResolvedValue({});
    const user = userEvent.setup();
    renderAt('/register');
    await fill(user);

    await user.click(submitButton());

    expect(await screen.findByText('elsewhere')).toBeInTheDocument();
    expect(screen.getByTestId('where')).toHaveTextContent('/account/orders');
    expect(register).toHaveBeenCalledTimes(1);
    expect(register.mock.calls[0][0]).toMatchObject({
      firstName: 'Nino',
      lastName: 'Beridze',
      email: 'nino@example.ge',
      password: 'sakartvelo',
    });
    expect(screen.getByText(t('auth.registered'))).toBeInTheDocument();
  });

  it('follows a safe redirect parameter', async () => {
    register.mockResolvedValue({});
    const user = userEvent.setup();
    renderAt('/register?redirect=%2Fcheckout');
    await fill(user);

    await user.click(submitButton());

    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent(/^\/checkout$/));
  });

  it.each([
    ['an absolute external URL', 'https://evil.example/steal'],
    ['a protocol-relative URL', '//evil.example'],
    ['a backslash variant', '/\\evil.example'],
  ])('does not follow %s', async (_name, target) => {
    register.mockResolvedValue({});
    const user = userEvent.setup();
    renderAt(`/register?redirect=${encodeURIComponent(target)}`);
    await fill(user);

    await user.click(submitButton());

    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent(/^\/account\/orders$/));
  });
});

describe('a refusal that belongs to no field', () => {
  it('shows the server message in a toast and stays on the form', async () => {
    register.mockRejectedValue(new Error('Server is on fire'));
    const user = userEvent.setup();
    renderAt('/register');
    await fill(user);

    await user.click(submitButton());

    expect(await screen.findByText('Server is on fire')).toBeInTheDocument();
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/register$/);
    expect(screen.queryByText(t('auth.registered'))).not.toBeInTheDocument();
  });

  it('falls back to the generic text when the error has no message', async () => {
    register.mockRejectedValue({});
    const user = userEvent.setup();
    renderAt('/register');
    await fill(user);

    await user.click(submitButton());

    expect(await screen.findByText(t('auth.registerFailed'))).toBeInTheDocument();
  });
});
