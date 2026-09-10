/**
 * useAdminSession: is the current visitor an administrator?
 *
 * What it does: asks the backend (`GET /admin/me`) rather than trusting the
 * stored session, and reports one of four states: checking, anonymous,
 * forbidden, admin.
 * Where it fits: RequireAdmin and AdminLayout consume it.
 * Notes: the role is deliberately not read from localStorage. The storefront
 * session does not carry it, and a value a user can edit is not an answer to
 * "may this person manage prices" - only the server's answer is.
 */

import { useCallback, useEffect, useState } from 'react';

import { getAdminProfile, isAdminAvailable } from './adminApi.js';
import { readSession } from '../services/session.js';

export function useAdminSession() {
  const [status, setStatus] = useState('checking');
  const [admin, setAdmin] = useState(null);

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
      const profile = await getAdminProfile();
      setAdmin(profile);
      setStatus('admin');
    } catch (error) {
      // 403 means signed in without the role; 401 means the session is gone —
      // the shared client has already tried a refresh by the time we see it.
      setStatus(error?.status === 403 ? 'forbidden' : 'anonymous');
      setAdmin(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!cancelled) await check();
    })();
    return () => {
      cancelled = true;
    };
  }, [check]);

  return { status, admin, recheck: check };
}
