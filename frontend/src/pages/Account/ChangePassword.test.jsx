/**
 * Tests for the change-password form.
 *
 * What they cover: the server ends every session of the account when the
 * password changes, so a success has to end it here too - the stored session
 * and the signed-in state - and send the person to the login page with the
 * reason. Left signed in, the next request gets a 401 at a random moment and
 * the person is sent to login with "session expired" and no explanation.
 * A rejected change (wrong current password) keeps the session.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';

vi.mock('virtual:api-impl', () => import('../../services/httpApi.js'));

import ChangePassword from './ChangePassword.jsx';
import { AuthProvider } from '../../context/AuthContext.jsx';
import { ToastProvider } from '../../context/ToastContext.jsx';
import ToastViewport from '../../components/common/Toast.jsx';
import { useAuth } from '../../hooks/useAuth.js';
import { readSession, writeSession } from '../../services/session.js';
import { t } from '../../i18n/index.js';

const reply = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

const USER = { id: 'u1', firstName: 'Nino', email: 'nino@example.ge' };

function Probe() {
  const { user } = useAuth();
  const location = useLocation();
  return (
    <>
      <p data-testid="user">{user ? user.email : 'guest'}</p>
      <p data-testid="where">{`${location.pathname}${location.search}`}</p>
    </>
  );
}

function renderForm() {
  return render(
    <ToastProvider>
      <AuthProvider>
        <MemoryRouter initialEntries={['/account/password']}>
          <Probe />
          <Routes>
            <Route path="/account/password" element={<ChangePassword />} />
            <Route path="/login" element={<p>login page</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
      <ToastViewport />
    </ToastProvider>,
  );
}

async function fillAndSubmit(user) {
  await user.type(screen.getByLabelText(t('account.currentPassword'), { exact: false }), 'OldPass123');
  await user.type(screen.getByLabelText(new RegExp('^' + t('auth.newPassword'))), 'NewPass456');
  await user.type(screen.getByLabelText(t('fields.repeatNewPassword'), { exact: false }), 'NewPass456');
  await user.click(screen.getByRole('button', { name: t('account.updatePassword') }));
}

beforeEach(() => {
  localStorage.clear();
  writeSession({ user: USER, token: 'tok' });
});

describe('a successful password change', () => {
  it('drops the session and the signed-in state and goes to login with the reason', async () => {
    global.fetch = vi.fn(async () => reply({ ok: true }));
    renderForm();
    expect(await screen.findByTestId('user')).toHaveTextContent(USER.email);

    await fillAndSubmit(userEvent.setup());

    await waitFor(() => expect(screen.getByText('login page')).toBeInTheDocument());
    expect(readSession()).toBeNull();
    expect(screen.getByTestId('user')).toHaveTextContent('guest');
    expect(screen.getByTestId('where')).toHaveTextContent(
      `/login?redirect=${encodeURIComponent('/account')}`,
    );
    expect(screen.getByText(t('account.passwordChangedSignIn'))).toBeInTheDocument();
  });
});

describe('a rejected password change', () => {
  it('keeps the session and stays on the page', async () => {
    global.fetch = vi.fn(async () =>
      reply({ error: { code: 'INVALID_CURRENT_PASSWORD', message: 'wrong password' } }, 400),
    );
    renderForm();
    expect(await screen.findByTestId('user')).toHaveTextContent(USER.email);

    await fillAndSubmit(userEvent.setup());

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole('button', { name: t('account.updatePassword') })).toBeEnabled());
    expect(readSession()).toEqual({ user: USER, token: 'tok' });
    expect(screen.getByTestId('user')).toHaveTextContent(USER.email);
    expect(screen.getByTestId('where')).toHaveTextContent('/account/password');
    expect(screen.queryByText('login page')).not.toBeInTheDocument();
  });
});
