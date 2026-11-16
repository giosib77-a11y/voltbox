/**
 * The footer lists top-level categories only. `/categories` is flat, with
 * `parentId`; a subcategory is reached from its parent, not listed beside it.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import Footer from './Footer.jsx';
import * as api from '../../services/api.js';
import { forgetDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { t } from '../../i18n/index.js';
import { formatPrice } from '../../utils/format.js';

const RULES = { cities: [], freeFrom: 50, currency: 'GEL' };

/**
 * The footer reads the delivery rules, which arrive after the first paint. A
 * test that ends before they do sees React update the page outside act(), so
 * each test renders and then waits for the free-delivery line the rules draw.
 */
async function renderFooter() {
  render(
    <MemoryRouter>
      <Footer categories={CATEGORIES} />
    </MemoryRouter>
  );
  await screen.findByText(t('footer.freeDelivery', { price: formatPrice(RULES.freeFrom) }));
}

beforeEach(() => {
  forgetDeliveryRules();
  vi.spyOn(api, 'getDeliveryRules').mockResolvedValue(RULES);
});

const CATEGORIES = [
  { id: 'c-phones', slug: 'phones', name: 'ტელეფონები', parentId: null },
  { id: 'c-samsung', slug: 'samsung', name: 'Samsung', parentId: 'c-phones' },
  { id: 'c-cables', slug: 'cables', name: 'კაბელები', parentId: null },
];

describe('Footer', () => {
  it('lists root categories and leaves subcategories out', async () => {
    await renderFooter();

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

    it('is shown in mock mode', async () => {
      vi.stubEnv('VITE_API_MODE', 'mock');
      await renderFooter();
      expect(screen.getByText(t('footer.demo'))).toBeInTheDocument();
    });

    it('is absent in http mode', async () => {
      vi.stubEnv('VITE_API_MODE', 'http');
      await renderFooter();
      expect(screen.queryByText(t('footer.demo'))).not.toBeInTheDocument();
    });
  });
});
