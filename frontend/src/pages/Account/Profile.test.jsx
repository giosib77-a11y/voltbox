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

vi.mock('../../hooks/useToast.js', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

beforeEach(() => {
  updateProfile.mockReset().mockResolvedValue({});
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
