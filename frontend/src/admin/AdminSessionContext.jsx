/**
 * AdminSessionContext: one answer to "is this visitor an admin?".
 *
 * What it does: performs the `GET /admin/me` check once and shares the result
 * with every admin component that needs it.
 * Where it fits: wraps the whole /admin tree, above RequireAdmin.
 * Notes: this replaces a per-component hook. RequireAdmin, AdminLayout and the
 * dashboard each called it, which meant three identical requests on every page
 * load - and the panel visibly waited for all of them before it drew.
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';

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
      // 403 means signed in without the role; 401 means the session is gone -
      // the shared client has already tried a refresh by the time we see it.
      setStatus(error?.status === 403 ? 'forbidden' : 'anonymous');
      setAdmin(null);
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  return (
    <AdminSessionContext.Provider value={{ status, admin, recheck: check }}>
      <Outlet />
    </AdminSessionContext.Provider>
  );
}
