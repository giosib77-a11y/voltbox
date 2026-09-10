/**
 * Tests for the admin route guard.
 *
 * What they cover: the four states RequireAdmin must resolve - still checking,
 * anonymous, signed in without the role, and admin - plus the rule that the
 * role is decided by the server rather than by anything in localStorage.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import RequireAdmin from './RequireAdmin.jsx';
import AdminSessionProvider from './AdminSessionContext.jsx';
import { __resetSessionStateForTests, writeSession } from '../services/session.js';

/**
 * Renders the guard at /admin/x with a stub page behind it.
 *
 * The provider sits above the guard, exactly as it does in App.jsx: the admin
 * check happens once there and is shared, so RequireAdmin only reads the result.
 */
function renderGuard() {
  return render(
    <MemoryRouter initialEntries={['/admin/x']}>
      <Routes>
        <Route path="/admin" element={<AdminSessionProvider />}>
          <Route element={<RequireAdmin />}>
            <Route path="x" element={<div>ადმინის გვერდი</div>} />
          </Route>
        </Route>
        <Route path="/admin/login" element={<div>ადმინის შესვლა</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

const reply = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

beforeEach(() => {
  __resetSessionStateForTests();
  localStorage.clear();
  vi.stubEnv('VITE_API_MODE', 'http');
});

describe('RequireAdmin', () => {
  it('shows a spinner while the role is still being checked', () => {
    writeSession({ user: { id: 'u1' }, token: 't', refreshToken: 'r' });
    // A promise that never settles keeps the guard in its checking state.
    global.fetch = vi.fn(() => new Promise(() => {}));

    renderGuard();

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByText('ადმინის გვერდი')).not.toBeInTheDocument();
  });

  it('redirects an anonymous visitor to the admin login, keeping the return path', async () => {
    global.fetch = vi.fn();

    renderGuard();

    expect(await screen.findByText('ადმინის შესვლა')).toBeInTheDocument();
    // No request is made when there is no token at all.
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('shows the 403 page for a signed-in customer', async () => {
    writeSession({ user: { id: 'u1' }, token: 't', refreshToken: 'r' });
    global.fetch = vi.fn(async () =>
      reply({ error: { code: 'ADMIN_REQUIRED', message: 'nope' } }, 403),
    );

    renderGuard();

    expect(await screen.findByText('წვდომა შეზღუდულია')).toBeInTheDocument();
    expect(screen.queryByText('ადმინის გვერდი')).not.toBeInTheDocument();
  });

  it('renders the page for an admin', async () => {
    writeSession({ user: { id: 'u1' }, token: 't', refreshToken: 'r' });
    global.fetch = vi.fn(async () =>
      reply({ id: 'u1', email: 'boss@voltbox.ge', role: 'admin', isActive: true }),
    );

    renderGuard();

    expect(await screen.findByText('ადმინის გვერდი')).toBeInTheDocument();
  });

  it('does not trust a role written into localStorage', async () => {
    // A user can edit this freely; only GET /admin/me decides.
    writeSession({ user: { id: 'u1', role: 'admin' }, token: 't', refreshToken: 'r' });
    global.fetch = vi.fn(async () =>
      reply({ error: { code: 'ADMIN_REQUIRED', message: 'nope' } }, 403),
    );

    renderGuard();

    await waitFor(() => expect(screen.getByText('წვდომა შეზღუდულია')).toBeInTheDocument());
  });
});
