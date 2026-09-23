/**
 * Tests for the shared admin session check.
 *
 * What they cover: the check has three answers and one non-answer. A 401 is
 * signed out, a 403 is signed in without the role - and a 5xx or a failed
 * connection is neither. Treating that last one as signed out showed the admin
 * the login form, as though they had been logged out, whenever the API failed.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';

import AdminSessionProvider from './AdminSessionContext.jsx';
import RequireAdmin from './RequireAdmin.jsx';
import {
  __resetSessionStateForTests,
  setSessionLostHandler,
  writeSession,
} from '../services/session.js';

/** The same tree as App.jsx: provider, then guard, then a page. */
function renderPanel() {
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

const ADMIN = { id: 'u1', email: 'boss@voltbox.ge', role: 'admin', isActive: true };

beforeEach(() => {
  __resetSessionStateForTests();
  localStorage.clear();
  vi.stubEnv('VITE_API_MODE', 'http');
  writeSession({ user: { id: 'u1' }, token: 't', refreshToken: 'r' });
});

describe('AdminSessionProvider', () => {
  it('does not show the login form when the check answers 500', async () => {
    global.fetch = vi.fn(async () =>
      reply({ error: { code: 'INTERNAL_ERROR', message: 'Internal server error' } }, 500),
    );

    renderPanel();

    expect(await screen.findByRole('alert')).toHaveTextContent('პანელი ვერ ჩაიტვირთა');
    expect(screen.queryByText('ადმინის შესვლა')).not.toBeInTheDocument();
    expect(screen.queryByText('ადმინის გვერდი')).not.toBeInTheDocument();
  });

  it('does not show the login form when the server cannot be reached', async () => {
    global.fetch = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });

    renderPanel();

    const alert = await screen.findByRole('alert');
    // httpClient's own words for a connection that never opened.
    expect(alert).toHaveTextContent('სერვერთან კავშირი ვერ დამყარდა');
    expect(screen.queryByText('ადმინის შესვლა')).not.toBeInTheDocument();
  });

  it('lets the admin retry, and enters the panel once the server answers', async () => {
    global.fetch = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    renderPanel();
    await screen.findByRole('alert');

    global.fetch = vi.fn(async () => reply(ADMIN));
    await userEvent.click(screen.getByRole('button', { name: 'ხელახლა ცდა' }));

    expect(await screen.findByText('ადმინის გვერდი')).toBeInTheDocument();
  });

  it('still sends a signed-out admin to the login form on a 401', async () => {
    // /admin/me and the refresh attempt both refuse: the session really is gone.
    global.fetch = vi.fn(async () =>
      reply({ error: { code: 'UNAUTHORIZED', message: 'Authentication required' } }, 401),
    );
    // The client's own reaction is a full-page redirect, which jsdom cannot do.
    const sessionLost = vi.fn();
    setSessionLostHandler(sessionLost);

    renderPanel();

    expect(await screen.findByText('ადმინის შესვლა')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(sessionLost).toHaveBeenCalled();
  });
});
