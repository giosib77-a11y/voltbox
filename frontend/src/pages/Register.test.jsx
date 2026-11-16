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
import { MemoryRouter } from 'react-router';

vi.mock('virtual:api-impl', () => import('../services/httpApi.js'));

const register = vi.fn();
vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({ register, pending: false }),
}));

import Register from './Register.jsx';
import { ToastProvider } from '../context/ToastContext.jsx';
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
