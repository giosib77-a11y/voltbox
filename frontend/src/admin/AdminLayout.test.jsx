/**
 * Tests for the admin frame.
 *
 * What they cover: a toast raised by an admin page is visible. The admin does
 * not use the storefront Layout, so AdminLayout must render the ToastViewport
 * itself; page tests that mock useToast cannot see it missing.
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';

import AdminLayout from './AdminLayout.jsx';
import { ToastProvider } from '../context/ToastContext.jsx';
import { useToast } from '../hooks/useToast.js';

vi.mock('./AdminSessionContext.jsx', () => ({
  useAdminSession: () => ({ admin: { email: 'boss@voltbox.ge' } }),
}));

function PageThatToasts() {
  const toast = useToast();
  return <button onClick={() => toast.success('შეკვეთა გადატანილია სანაგვეში')}>go</button>;
}

describe('AdminLayout', () => {
  it('shows a toast raised by the page inside it', async () => {
    render(
      <ToastProvider>
        <MemoryRouter initialEntries={['/admin/x']}>
          <Routes>
            <Route path="/admin" element={<AdminLayout />}>
              <Route path="x" element={<PageThatToasts />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ToastProvider>,
    );

    screen.getByRole('button', { name: 'go' }).click();

    expect(await screen.findByText('შეკვეთა გადატანილია სანაგვეში')).toBeInTheDocument();
  });
});
