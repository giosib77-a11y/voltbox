// First: it reads the language from the address, and every module below may
// translate as soon as it runs.
import './i18n/index.js';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App.jsx';
import ErrorBoundary from './components/common/ErrorBoundary.jsx';
import { ToastProvider } from './context/ToastContext.jsx';
import { AuthProvider } from './context/AuthContext.jsx';
import { CartProvider } from './context/CartContext.jsx';
import CartAccountSync from './context/CartAccountSync.jsx';

import './index.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <ToastProvider>
        <AuthProvider>
          <CartProvider>
            <CartAccountSync />
            <App />
          </CartProvider>
        </AuthProvider>
      </ToastProvider>
    </ErrorBoundary>
  </StrictMode>,
);
