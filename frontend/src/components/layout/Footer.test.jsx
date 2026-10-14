/**
 * The footer lists top-level categories only. `/categories` is flat, with
 * `parentId`; a subcategory is reached from its parent, not listed beside it.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import Footer from './Footer.jsx';
import { t } from '../../i18n/index.js';

const CATEGORIES = [
  { id: 'c-phones', slug: 'phones', name: 'ტელეფონები', parentId: null },
  { id: 'c-samsung', slug: 'samsung', name: 'Samsung', parentId: 'c-phones' },
  { id: 'c-cables', slug: 'cables', name: 'კაბელები', parentId: null },
];

describe('Footer', () => {
  it('lists root categories and leaves subcategories out', () => {
    render(
      <MemoryRouter>
        <Footer categories={CATEGORIES} />
      </MemoryRouter>
    );

    const nav = screen.getByRole('navigation', { name: 'კატეგორიები (ქვედა მენიუ)' });
    const names = within(nav)
      .getAllByRole('link')
      .map((link) => link.textContent);
    expect(names).toEqual(['ტელეფონები', 'კაბელები']);
  });

  describe('demo notice', () => {
    afterEach(() => {
      vi.unstubAllEnvs();
    });

    const renderFooter = () =>
      render(
        <MemoryRouter>
          <Footer categories={CATEGORIES} />
        </MemoryRouter>
      );

    it('is shown in mock mode', () => {
      vi.stubEnv('VITE_API_MODE', 'mock');
      renderFooter();
      expect(screen.getByText(t('footer.demo'))).toBeInTheDocument();
    });

    it('is absent in http mode', () => {
      vi.stubEnv('VITE_API_MODE', 'http');
      renderFooter();
      expect(screen.queryByText(t('footer.demo'))).not.toBeInTheDocument();
    });
  });
});
