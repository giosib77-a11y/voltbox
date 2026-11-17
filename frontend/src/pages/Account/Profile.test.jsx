/**
 * Tests for the profile form.
 *
 * What they cover: changing the email asks for the current password and sends
 * it; saving anything else does not. The server refuses an email change
 * without the password, so a form that forgot to ask would fail at the very
 * last step with an error the person cannot act on.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import Profile from './Profile.jsx';
import * as httpApi from '../../services/httpApi.js';
import { t } from '../../i18n/index.js';

const updateProfile = vi.fn();

// One object for every render: the form re-reads `user` in an effect, so a fresh
// object each call would reset what was typed on every keystroke.
const user = {
  firstName: 'ნინო',
  lastName: 'კაპანაძე',
  email: 'nino@example.ge',
  phone: '555123456',
};
const auth = { user, updateProfile };

vi.mock('../../hooks/useAuth.js', () => ({ useAuth: () => auth }));

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock('../../hooks/useToast.js', () => ({ useToast: () => toast }));

beforeEach(() => {
  updateProfile.mockReset().mockResolvedValue({});
  toast.success.mockReset();
  toast.error.mockReset();
});

const passwordField = () => screen.queryByLabelText(new RegExp(t('account.currentPassword')));

describe('the profile form', () => {
  it('does not ask for the password while the email is unchanged', async () => {
    render(<Profile />);

    expect(passwordField()).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: t('common.save') }));

    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1));
    expect(updateProfile.mock.calls[0][0]).not.toHaveProperty('currentPassword');
  });

  it('asks for it once the email differs, and sends it', async () => {
    render(<Profile />);
    const email = screen.getByLabelText(new RegExp(t('fields.email')));

    await userEvent.clear(email);
    await userEvent.type(email, 'new@example.ge');
    await userEvent.type(passwordField(), 'supersecret1');
    await userEvent.click(screen.getByRole('button', { name: t('common.save') }));

    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1));
    expect(updateProfile.mock.calls[0][0]).toMatchObject({
      email: 'new@example.ge',
      currentPassword: 'supersecret1',
    });
  });

  it('does not send a changed email without the password', async () => {
    render(<Profile />);
    const email = screen.getByLabelText(new RegExp(t('fields.email')));

    await userEvent.clear(email);
    await userEvent.type(email, 'new@example.ge');
    await userEvent.click(screen.getByRole('button', { name: t('common.save') }));

    expect(updateProfile).not.toHaveBeenCalled();
  });
});

// The real API answers with the code and no per-field details, so these go
// through the real http client with a mocked fetch reply.
describe('a refusal from the real API', () => {
  const reply = (body, status) => ({
    ok: false,
    status,
    json: async () => body,
  });

  async function submitChangedEmail() {
    updateProfile.mockImplementation(httpApi.updateProfile);
    render(<Profile />);
    const email = screen.getByLabelText(new RegExp(t('fields.email')));
    await userEvent.clear(email);
    await userEvent.type(email, 'taken@example.ge');
    await userEvent.type(passwordField(), 'supersecret1');
    await userEvent.click(screen.getByRole('button', { name: t('common.save') }));
    return email;
  }

  // The error id comes first in aria-describedby; a hint id may follow it.
  const messageOf = (field) => document.getElementById(field.getAttribute('aria-describedby').split(' ')[0]);

  it('shows a taken email at the email field, with no toast', async () => {
    global.fetch = vi.fn(async () =>
      reply({ error: { code: 'EMAIL_ALREADY_EXISTS', message: 'email taken' } }, 409),
    );

    const email = await submitChangedEmail();

    await waitFor(() => expect(email).toHaveAttribute('aria-invalid', 'true'));
    expect(messageOf(email)).toHaveTextContent(t('apiErrors.EMAIL_ALREADY_EXISTS'));
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('shows a wrong current password at its own field, with no toast', async () => {
    global.fetch = vi.fn(async () =>
      reply(
        {
          error: {
            code: 'INVALID_CURRENT_PASSWORD',
            message: 'wrong password',
            details: [{ field: 'currentPassword', message: 'wrong password' }],
          },
        },
        400,
      ),
    );

    await submitChangedEmail();

    const field = passwordField();
    await waitFor(() => expect(field).toHaveAttribute('aria-invalid', 'true'));
    expect(messageOf(field)).toHaveTextContent(t('apiErrors.INVALID_CURRENT_PASSWORD'));
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('still toasts a refusal that belongs to no field', async () => {
    global.fetch = vi.fn(async () => reply({ error: { code: 'INTERNAL_ERROR', message: 'boom' } }, 500));

    await submitChangedEmail();

    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1));
  });
});
