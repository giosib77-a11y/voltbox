/**
 * AdminSessionContext: one answer to "is this visitor an admin?".
 *
 * What it does: performs the `GET /admin/me` check once and shares the result
 * with every admin component that needs it.
 * Where it fits: wraps the protected /admin tree, above RequireAdmin.
 * Notes: this replaces a per-component hook. RequireAdmin, AdminLayout and the
 * dashboard each called it, which meant three identical requests on every page
 * load - and the panel visibly waited for all of them before it drew.
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { Outlet } from 'react-router';

import { getAdminProfile, isAdminAvailable } from './adminApi.js';
import { readSession } from '../services/session.js';

const AdminSessionContext = createContext(null);

export function useAdminSession() {
  const value = useContext(AdminSessionContext);
  if (value === null) {
    throw new Error('useAdminSession must be used inside AdminSessionProvider');
  }
  return value;
}

export default function AdminSessionProvider() {
  const [status, setStatus] = useState('checking');
  const [admin, setAdmin] = useState(null);
  const [problem, setProblem] = useState(null);

  const check = useCallback(async () => {
    if (!isAdminAvailable()) {
      setStatus('unavailable');
      return;
    }
    if (!readSession()?.token) {
      setStatus('anonymous');
      return;
    }
    try {
      setAdmin(await getAdminProfile());
      setStatus('admin');
    } catch (error) {
      setAdmin(null);
      // 403 means signed in without the role; 401 means the session is gone -
      // the shared client has already tried a refresh by the time we see it.
      if (error?.status === 403) setStatus('forbidden');
      else if (error?.status === 401) setStatus('anonymous');
      else {
        // A 5xx, a dropped connection or a timeout says nothing about the
        // session. Sending the admin to the login form would read as a logout
        // and hide the real cause until they had typed their password again.
        setProblem(error?.message || 'სერვერმა ვერ უპასუხა.');
        setStatus('unreachable');
      }
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  // Back to the spinner only from the failure screen: a recheck from anywhere
  // else must not unmount a page that is already drawn.
  const retry = useCallback(() => {
    setStatus('checking');
    check();
  }, [check]);

  return (
    <AdminSessionContext.Provider value={{ status, admin, recheck: check }}>
      {status === 'unreachable' ? (
        <SessionCheckFailed message={problem} onRetry={retry} />
      ) : (
        <Outlet />
      )}
    </AdminSessionContext.Provider>
  );
}

/**
 * The check itself failed, so there is no answer yet - not signed out, not
 * forbidden. Drawn here rather than in RequireAdmin because nothing under the
 * provider can render meaningfully without that answer, and the retry is the
 * provider's own check.
 */
function SessionCheckFailed({ message, onRetry }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
      <div role="alert" className="w-full max-w-sm rounded-xl border border-ink-200 bg-white p-6 text-center">
        <h1 className="text-base font-semibold text-ink-900">პანელი ვერ ჩაიტვირთა</h1>
        <p className="mt-2 text-sm text-ink-600">{message}</p>
        <p className="mt-1 text-sm text-ink-500">სესია არ დაკარგულა — ხელახლა შესვლა საჭირო არაა.</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 w-full rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700"
        >
          ხელახლა ცდა
        </button>
      </div>
    </main>
  );
}
