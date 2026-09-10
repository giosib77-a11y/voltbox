/**
 * AdminLogin: sign-in for the admin panel.
 *
 * What it does: uses the same /auth/login endpoint as the storefront, then
 * confirms the account really is an admin before entering the panel.
 * Where it fits: /admin/login, outside RequireAdmin.
 * Notes: a successful login by a customer must not drop them into the shell —
 * every request would answer 403 and the panel would look broken. The role is
 * confirmed against GET /admin/me, never against the stored session.
 */

import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2, Store } from 'lucide-react';

import * as api from '../../services/api.js';
import { getAdminProfile } from '../adminApi.js';
import { clearSession } from '../../services/session.js';

export default function AdminLogin() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);

  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get('next') || '/admin';

  async function handleSubmit(event) {
    event.preventDefault();
    if (pending) return;

    setPending(true);
    setError(null);
    try {
      await api.login({ email: email.trim(), password });
      // Logged in, but is this an admin? Ask the server, not the session.
      await getAdminProfile();
      navigate(next, { replace: true });
    } catch (caught) {
      if (caught?.status === 403) {
        // Signed in as a customer: drop the session so the storefront header
        // does not silently show them as logged in from an admin login page.
        clearSession();
        setError('ამ ანგარიშს ადმინისტრატორის უფლებები არ აქვს.');
      } else if (caught?.status === 401) {
        setError('ელ. ფოსტა ან პაროლი არასწორია.');
      } else {
        setError(caught?.message || 'შესვლა ვერ მოხერხდა. სცადეთ ხელახლა.');
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
      <form onSubmit={handleSubmit} noValidate className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2">
          <Store className="h-6 w-6 text-accent-600" aria-hidden="true" />
          <span className="text-lg font-semibold text-ink-900">VoltBox</span>
          <span className="rounded bg-ink-100 px-1.5 py-0.5 text-xs font-medium text-ink-600">
            ადმინი
          </span>
        </div>

        <div className="rounded-xl border border-ink-200 bg-white p-6">
          <label htmlFor="admin-email" className="block text-sm font-medium text-ink-800">
            ელ. ფოსტა
          </label>
          <input
            id="admin-email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-1 w-full rounded-lg border border-ink-300 px-3 py-2 text-sm focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/30"
          />

          <label htmlFor="admin-password" className="mt-4 block text-sm font-medium text-ink-800">
            პაროლი
          </label>
          <input
            id="admin-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full rounded-lg border border-ink-300 px-3 py-2 text-sm focus:border-accent-600 focus:outline-none focus:ring-2 focus:ring-accent-600/30"
          />

          {error ? (
            <p role="alert" className="mt-4 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={pending}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700"
          >
            {pending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
            შესვლა
          </button>
        </div>

        <p className="mt-4 text-center text-sm text-ink-500">
          <Link to="/" className="hover:text-ink-700">
            მაღაზიაში დაბრუნება
          </Link>
        </p>
      </form>
    </main>
  );
}
