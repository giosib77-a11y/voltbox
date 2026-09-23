/**
 * Tests for the admin sign-in form.
 *
 * What they cover: the three ways the server can refuse, and that each one
 * reaches the reader as the thing that actually happened. Two of them are 401s
 * and only the error's code tells them apart - a wrong password, and an account
 * locked after too many attempts. Collapsing both into "wrong password" leaves
 * the shop's owner retyping a password that is correct.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';

import AdminLogin from './AdminLogin.jsx';
import * as api from '../../services/api.js';
import * as adminApi from '../adminApi.js';
import { __resetSessionStateForTests, writeSession } from '../../services/session.js';

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/admin/login']}>
      <AdminLogin />
    </MemoryRouter>,
  );
}

async function signIn() {
  await userEvent.type(screen.getByLabelText('ელ. ფოსტა'), 'boss@voltbox.ge');
  await userEvent.type(screen.getByLabelText('პაროლი'), 'supersecret1');
  await userEvent.click(screen.getByRole('button', { name: 'შესვლა' }));
}

/** What httpClient throws: the code lives under `details`. */
const refusal = (status, code, message) =>
  Object.assign(new Error(message), { status, details: { code } });

beforeEach(() => {
  __resetSessionStateForTests();
  vi.restoreAllMocks();
});

describe('AdminLogin', () => {
  it('says the password was wrong when it was', async () => {
    vi.spyOn(api, 'login').mockRejectedValue(
      refusal(401, 'INVALID_CREDENTIALS', 'ელ. ფოსტა ან პაროლი არასწორია'),
    );
    renderLogin();

    await signIn();

    expect(await screen.findByRole('alert')).toHaveTextContent('ელ. ფოსტა ან პაროლი არასწორია.');
  });

  it('passes on the lockout message instead of blaming the password', async () => {
    vi.spyOn(api, 'login').mockRejectedValue(
      refusal(
        401,
        'TOO_MANY_LOGIN_ATTEMPTS',
        'ბევრი წარუმატებელი მცდელობა. სცადეთ 15 წუთში.',
      ),
    );
    renderLogin();

    await signIn();

    expect(await screen.findByRole('alert')).toHaveTextContent('სცადეთ 15 წუთში.');
  });

  it('tells a customer who signs in here that they are not an administrator', async () => {
    vi.spyOn(api, 'login').mockResolvedValue({});
    vi.spyOn(adminApi, 'getAdminProfile').mockRejectedValue(
      refusal(403, 'ADMIN_REQUIRED', 'Administrator access required'),
    );
    renderLogin();

    await signIn();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'ამ ანგარიშს ადმინისტრატორის უფლებები არ აქვს.',
    );
  });

  describe('when a stored session is checked on arrival', () => {
    beforeEach(() => {
      writeSession({ user: { id: 'u1' }, token: 't', refreshToken: 'r' });
    });

    it('says the server failed instead of silently showing the form', async () => {
      vi.spyOn(adminApi, 'getAdminProfile').mockRejectedValue(
        refusal(500, 'INTERNAL_ERROR', 'სერვერის შეცდომა'),
      );
      renderLogin();

      expect(await screen.findByRole('alert')).toHaveTextContent('სერვერის შეცდომა');
    });

    it('stays quiet for an expired session - the form is the right answer', async () => {
      const check = vi
        .spyOn(adminApi, 'getAdminProfile')
        .mockRejectedValue(refusal(401, 'UNAUTHORIZED', 'Authentication required'));
      renderLogin();

      await waitFor(() => expect(check).toHaveBeenCalled());
      await Promise.resolve();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });
});
