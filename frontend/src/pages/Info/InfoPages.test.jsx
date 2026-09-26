/**
 * The four information pages, each mounted on its own.
 *
 * What they cover: the delivery prices come from GET /delivery and from
 * nowhere else - a different answer draws a different table; the parts that
 * follow the email switch (the FAQ's forgotten-password answer, Resend in the
 * privacy list); that no page shows a placeholder from its source text; and
 * that a fact listed in docs/info-pages-todo.md stays hidden until it is
 * written into SHOP_FACTS, then appears.
 * Notes: the API is the real http client over a stubbed fetch, so a fixture is
 * the response body as the server sends it - money as strings.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import DeliveryTerms from './DeliveryTerms.jsx';
import ReturnsWarranty from './ReturnsWarranty.jsx';
import Privacy from './Privacy.jsx';
import Faq from './Faq.jsx';
import { CONTACT, SHOP_FACTS } from '../../constants/index.js';
import { forgetDeliveryRules, loadDeliveryRules } from '../../hooks/useDeliveryRules.js';

vi.mock('virtual:api-impl', () => import('../../services/httpApi.js'));

const PAGES = [
  ['delivery', DeliveryTerms],
  ['returns', ReturnsWarranty],
  ['privacy', Privacy],
  ['faq', Faq],
];

const TBILISI_RUSTAVI = {
  cities: [
    { name: 'თბილისი', fee: '8.00' },
    { name: 'რუსთავი', fee: '5.00' },
  ],
  freeFrom: '50.00',
};

const BATUMI = {
  cities: [{ name: 'ბათუმი', fee: '12.50' }],
  freeFrom: '80.00',
};

/** GET /delivery. */
const rules = ({ cities, freeFrom } = TBILISI_RUSTAVI, email = false) => ({
  cities,
  freeFrom,
  currency: 'GEL',
  features: { email },
});

function answer(body) {
  global.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => body }));
}

/** Until the rules have arrived and the page has redrawn. */
async function rulesSettled() {
  await act(async () => {
    await loadDeliveryRules().catch(() => {});
  });
}

async function mount(Page) {
  const view = render(
    <MemoryRouter>
      <Page />
    </MemoryRouter>,
  );
  await rulesSettled();
  return view;
}

/** The delivery table's body, as [city, fee] pairs. */
function tableRows() {
  const table = screen.getByRole('table', { name: 'მიწოდების ღირებულება ქალაქების მიხედვით' });
  return within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) => [...row.children].map((cell) => cell.textContent));
}

/** The FAQ entry on a forgotten password, question and answer. */
const passwordAnswer = () =>
  screen.getByRole('heading', { name: 'პაროლი დამავიწყდა, რა ვქნა?' }).closest('section');

const returnSteps = () => screen.getByRole('list', { name: 'როგორ დავაბრუნოთ:' });

const UNKNOWN = { ...SHOP_FACTS };

beforeEach(() => {
  forgetDeliveryRules();
});

afterEach(() => {
  Object.assign(SHOP_FACTS, UNKNOWN);
});

describe('delivery prices', () => {
  it.each([
    [
      'Tbilisi and Rustavi',
      TBILISI_RUSTAVI,
      [
        ['თბილისი', '8 ₾'],
        ['რუსთავი', '5 ₾'],
        ['შეკვეთა 50 ₾-დან', 'უფასო'],
      ],
    ],
    [
      'Batumi alone, dearer',
      BATUMI,
      [
        ['ბათუმი', '12.50 ₾'],
        ['შეკვეთა 80 ₾-დან', 'უფასო'],
      ],
    ],
  ])('the delivery page draws the table GET /delivery sends: %s', async (_, fixture, expected) => {
    answer(rules(fixture));
    await mount(DeliveryTerms);

    expect(global.fetch).toHaveBeenCalledWith(expect.stringMatching(/\/delivery$/), expect.anything());
    expect(tableRows()).toEqual(expected);
  });

  it('the FAQ prices and names the cities from the same answer', async () => {
    answer(rules(BATUMI));
    await mount(Faq);

    expect(tableRows()).toEqual([
      ['ბათუმი', '12.50 ₾'],
      ['შეკვეთა 80 ₾-დან', 'უფასო'],
    ]);
    expect(screen.getByText('ცხრილში ჩამოთვლილ ქალაქებში: ბათუმი.')).toBeInTheDocument();
  });
});

describe('placeholders', () => {
  describe.each([false, true])('with email %s', (email) => {
    it.each(PAGES)('the %s page shows none', async (_, Page) => {
      answer(rules(TBILISI_RUSTAVI, email));
      const { container } = await mount(Page);

      expect(container.textContent.length).toBeGreaterThan(0);
      expect(container.innerHTML).not.toContain('{{');
      expect(container.innerHTML).not.toContain('MISSING');
    });
  });
});

describe('the email switch', () => {
  it('while off, the FAQ sends a forgotten password to the phone', async () => {
    answer(rules(TBILISI_RUSTAVI, false));
    await mount(Faq);

    const reply = passwordAnswer();
    expect(reply).toHaveTextContent(/პაროლის აღდგენა ამჟამად მიუწვდომელია/);
    expect(within(reply).getByRole('link', { name: CONTACT.phone })).toHaveAttribute(
      'href',
      CONTACT.phoneHref,
    );
    expect(screen.queryByRole('link', { name: '„დაგავიწყდათ პაროლი?“' })).not.toBeInTheDocument();
  });

  it('while on, the FAQ sends it to the reset form', async () => {
    answer(rules(TBILISI_RUSTAVI, true));
    await mount(Faq);

    expect(screen.getByRole('link', { name: '„დაგავიწყდათ პაროლი?“' })).toHaveAttribute(
      'href',
      '/forgot-password',
    );
    expect(screen.queryByText(/პაროლის აღდგენა ამჟამად მიუწვდომელია/)).not.toBeInTheDocument();
  });

  it.each([
    [false, false],
    [true, true],
  ])('with email %s, the privacy page lists Resend: %s', async (email, listed) => {
    answer(rules(TBILISI_RUSTAVI, email));
    await mount(Privacy);

    const resend = screen.queryByText(/^Resend/);
    if (listed) expect(resend).toBeInTheDocument();
    else expect(resend).not.toBeInTheDocument();
  });
});

describe('facts the owner has not supplied yet', () => {
  it('leave their sentences out', async () => {
    answer(rules());

    const delivery = await mount(DeliveryTerms);
    expect(screen.queryByText(/მიიტანება/)).not.toBeInTheDocument();
    delivery.unmount();

    const returns = await mount(ReturnsWarranty);
    expect(within(returnSteps()).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.queryByText(/ვადით/)).not.toBeInTheDocument();
    returns.unmount();

    const privacy = await mount(Privacy);
    expect(screen.queryByRole('heading', { name: 'ვინ ვართ' })).not.toBeInTheDocument();
    privacy.unmount();

    await mount(Faq);
    expect(screen.queryByRole('heading', { name: 'რამდენ ხანში მომივა?' })).not.toBeInTheDocument();
  });

  it('appear once written into SHOP_FACTS', async () => {
    Object.assign(SHOP_FACTS, {
      deliveryDays: '1–3',
      returnPickup: 'კურიერი პროდუქტს თქვენი მისამართიდან წაიღებს',
      warrantyPeriod: 'ერთი წელი',
      legalEntity: { name: 'შპს ვოლტბოქსი', idCode: '400000000', address: 'თბილისი' },
    });
    answer(rules());

    const delivery = await mount(DeliveryTerms);
    expect(screen.getByText(/შეკვეთა მიიტანება 1–3 სამუშაო დღეში\./)).toBeInTheDocument();
    delivery.unmount();

    const returns = await mount(ReturnsWarranty);
    const steps = within(returnSteps()).getAllByRole('listitem');
    expect(steps).toHaveLength(3);
    expect(steps[1]).toHaveTextContent('კურიერი პროდუქტს თქვენი მისამართიდან წაიღებს');
    expect(screen.getByText('პროდუქტზე ვრცელდება გარანტია, ვადით ერთი წელი.')).toBeInTheDocument();
    returns.unmount();

    const privacy = await mount(Privacy);
    expect(screen.getByRole('heading', { name: 'ვინ ვართ' })).toBeInTheDocument();
    expect(screen.getByText('400000000')).toBeInTheDocument();
    privacy.unmount();

    await mount(Faq);
    expect(screen.getByRole('heading', { name: 'რამდენ ხანში მომივა?' })).toBeInTheDocument();
    expect(screen.getByText('1–3 სამუშაო დღეში.')).toBeInTheDocument();
  });
});
