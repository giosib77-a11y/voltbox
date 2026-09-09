import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

/**
 * Toast-ების გლობალური რიგი.
 * მხარს უჭერს ქმედების ღილაკს (მაგ. „დაბრუნება“ წაშლის გაუქმებისთვის).
 */

const ToastContext = createContext(null);

const DEFAULT_DURATION = 4000;
let nextId = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback(
    ({ message, type = 'info', duration = DEFAULT_DURATION, action = null }) => {
      nextId += 1;
      const id = nextId;
      setToasts((current) => [...current.slice(-3), { id, message, type, action }]);

      if (duration > 0) {
        const timer = setTimeout(() => {
          setToasts((c) => c.filter((t) => t.id !== id));
          timers.current.delete(id);
        }, duration);
        timers.current.set(id, timer);
      }
      return id;
    },
    [],
  );

  const value = useMemo(
    () => ({
      toasts,
      dismiss,
      push,
      success: (message, options = {}) => push({ ...options, message, type: 'success' }),
      error: (message, options = {}) => push({ ...options, message, type: 'error' }),
      info: (message, options = {}) => push({ ...options, message, type: 'info' }),
    }),
    [toasts, dismiss, push],
  );

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast უნდა გამოიძახოთ <ToastProvider> -ის შიგნით');
  return context;
}

export default ToastContext;
