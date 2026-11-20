/**
 * The product page names one warranty: the shop's own, WARRANTY_MONTHS months
 * on every product. A product (the owner's live data, or old mock data) may
 * still carry a `specs.warranty` of its own; the page must neither show it as
 * the term nor list it in the specs table, or it would contradict the rule.
 *
 * The fourth badge is payment on delivery, true in every city. The page makes
 * no claim of originality or of a manufacturer's warranty.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';

import { WARRANTY_MONTHS } from '../constants/index.js';
import { t } from '../i18n/index.js';
import { forgetCategories } from '../hooks/useProducts.js';
import { forgetDeliveryRules } from '../hooks/useDeliveryRules.js';
import { formatPrice } from '../utils/format.js';
import * as api from '../services/api.js';
import ProductDetails from './ProductDetails.jsx';

vi.mock('../hooks/useCart.js', () => ({ useCart: () => ({ addItem: () => {}, quantities: {} }) }));
vi.mock('../hooks/useToast.js', () => ({ useToast: () => ({ success: () => {}, error: () => {} }) }));

const CITIES = [
  { name: 'თბილისი', fee: 8 },
  { name: 'რუსთავი', fee: 5 },
];

const PRODUCT = {
  id: 'p-1',
  slug: 'anker-nano',
  name: 'Anker Nano 20W',
  brand: 'Anker',
  category: 'chargers',
  shortDescription: '20W PD',
  description: 'A small charger.',
  price: 45,
  oldPrice: null,
  hasDiscount: false,
  discountPercent: 0,
  images: [],
  rating: 0,
  reviewsCount: 0,
  inStock: true,
  isLowStock: false,
  stock: 5,
  tags: [],
  // The old per-product term that must not show
  specs: { power: '20 W', warranty: '24 თვე' },
};

beforeEach(() => {
  forgetCategories();
  forgetDeliveryRules();
  vi.spyOn(api, 'getProductBySlug').mockResolvedValue(PRODUCT);
  vi.spyOn(api, 'getRelatedProducts').mockResolvedValue([]);
  vi.spyOn(api, 'getCategories').mockResolvedValue([]);
  vi.spyOn(api, 'getDeliveryRules').mockResolvedValue({ cities: CITIES, freeFrom: 100, currency: 'GEL' });
});

afterEach(() => vi.restoreAllMocks());

async function mount() {
  render(
    <MemoryRouter initialEntries={['/product/anker-nano']}>
      <Routes>
        <Route path="/product/:slug" element={<ProductDetails />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { level: 1, name: PRODUCT.name });
}

describe('the product page badges', () => {
  it('shows the shop warranty even when the product carries a spec of its own', async () => {
    await mount();

    expect(screen.getByText(t('product.warranty', { months: WARRANTY_MONTHS }))).toBeInTheDocument();
    expect(screen.getByText(`${WARRANTY_MONTHS} თვის გარანტია`)).toBeInTheDocument();
    expect(screen.queryByText(/24 თვე/)).not.toBeInTheDocument();
  });

  it('the fourth badge is payment on delivery, not originality', async () => {
    await mount();

    expect(screen.getByText('გადახდა მიღებისას')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/ორიგინალ|ოფიციალ|მწარმოებლ/);
  });
});

describe('the product page tabs', () => {
  it('the specs table skips the per-product warranty and keeps the other specs', async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole('tab', { name: t('product.tabs.specs') }));

    const table = screen.getByRole('table');
    expect(within(table).getByText('20 W')).toBeInTheDocument();
    expect(within(table).queryByText('24 თვე')).not.toBeInTheDocument();
    expect(within(table).queryByRole('rowheader', { name: /გარანტია/ })).not.toBeInTheDocument();
  });

  it('the delivery tab states the shop warranty beside the legal 2 years, and the city fees', async () => {
    const user = userEvent.setup();
    await mount();
    await user.click(screen.getByRole('tab', { name: t('product.tabs.delivery') }));

    const panel = screen.getByRole('tabpanel');
    expect(panel).toHaveTextContent(t('deliveryInfo.warrantyText', { months: WARRANTY_MONTHS }));
    expect(panel).toHaveTextContent('2 წელია');
    expect(panel).toHaveTextContent(`თბილისი — ${formatPrice(8)}, რუსთავი — ${formatPrice(5)}`);
    expect(panel.textContent).not.toMatch(/მწარმოებლ|აღწერაშია|\{\{/);
  });
});
