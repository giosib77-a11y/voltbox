import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as api from '../services/api.js';

/**
 * ავტორიზაციის მდგომარეობა.
 *
 * ⚠️  MOCK ONLY — replace with real auth API.
 *     სესია ინახება localStorage-ში (`auth:v1`); რეალურ backend-ზე
 *     გადასვლისას `services/httpApi.js` იმავე ხელმოწერებს ინარჩუნებს.
 */

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);
  const [pending, setPending] = useState(false);

  // სესიის სინქრონული აღდგენა — ქსელის მოლოდინის გარეშე
  useEffect(() => {
    const session = api.getSessionSync?.();
    if (session?.user) setUser(session.user);
    setInitializing(false);
  }, []);

  const login = useCallback(async (credentials) => {
    setPending(true);
    try {
      const session = await api.login(credentials);
      setUser(session.user);
      return session.user;
    } finally {
      setPending(false);
    }
  }, []);

  const register = useCallback(async (payload) => {
    setPending(true);
    try {
      const session = await api.register(payload);
      setUser(session.user);
      return session.user;
    } finally {
      setPending(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setPending(true);
    try {
      await api.logout();
      setUser(null);
    } finally {
      setPending(false);
    }
  }, []);

  const updateProfile = useCallback(async (patch) => {
    const updated = await api.updateProfile(patch);
    setUser(updated);
    return updated;
  }, []);

  const changePassword = useCallback((payload) => api.changePassword(payload), []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      initializing,
      pending,
      login,
      register,
      logout,
      updateProfile,
      changePassword,
    }),
    [user, initializing, pending, login, register, logout, updateProfile, changePassword],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth უნდა გამოიძახოთ <AuthProvider> -ის შიგნით');
  return context;
}

export default AuthContext;
