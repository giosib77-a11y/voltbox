/**
 * Tests that the signed-in state follows a session the HTTP client ended.
 *
 * What they cover: session.js clears the stored session when a refresh fails,
 * but AuthContext restored its user from storage once on mount. Unless it hears
 * about the clear, the header keeps showing a signed-in shopper and
 * CartAccountSync never treats it as a sign-out.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';

import { AuthProvider } from './AuthContext.jsx';
import { useAuth } from '../hooks/useAuth.js';
import { request } from '../services/httpClient.js';
import { __resetSessionStateForTests, setSessionLostHandler, writeSession } from '../services/session.js';

function Probe() {
  const { user } = useAuth();
  return <span data-testid="who">{user ? user.id : 'guest'}</span>;
}

beforeEach(() => {
  __resetSessionStateForTests();
  localStorage.clear();
});

describe('AuthProvider and an ended session', () => {
  it('drops the user when a background request finds the session dead', async () => {
    writeSession({ user: { id: 'u1', email: 'a@b.ge' }, token: 'expired' });
    const lost = vi.fn();
    setSessionLostHandler(lost);
    global.fetch = vi.fn(async (url) => ({
      ok: false,
      status: 401,
      json: async () => ({ error: { code: 'INVALID_TOKEN' } }),
      url,
    }));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(screen.getByTestId('who')).toHaveTextContent('u1');

    await act(async () => {
      await request('/cart', { background: true }).catch(() => {});
    });

    expect(screen.getByTestId('who')).toHaveTextContent('guest');
    expect(lost).not.toHaveBeenCalled();
  });
});
