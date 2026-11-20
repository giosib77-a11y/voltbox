/**
 * The four information pages, each mounted on its own.
 *
 * What they cover: the delivery prices come from GET /delivery and from
 * nowhere else - a different answer draws a different table; the parts that
 * follow the email switch (the FAQ's forgotten-password answer, Resend in the
 * privacy list); that no page shows a placeholder from its source text; and
 * that a fact listed in docs/info-pages-todo.md stays hidden until it is
 * written into SHOP_FACTS, then appears; the delivery time is `shipping.etaDays`'s, the one the cart shows; and that what the privacy page says is stored, sent to
 * Telegram and asked at registration is read from the code that does it.
 * Notes: the API is the real http client over a stubbed fetch, so a fixture is
 * the response body as the server sends it - money as strings.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import DeliveryTerms from './DeliveryTerms.jsx';
import ReturnsWarranty from './ReturnsWarranty.jsx';
import Privacy from './Privacy.jsx';
import Faq from './Faq.jsx';
import { CONTACT, SHOP_FACTS, STORAGE_KEYS, WARRANTY_MONTHS } from '../../constants/index.js';
import { formatPrice } from '../../utils/format.js';
import { i18n, t } from '../../i18n/index.js';
import { forgetDeliveryRules, loadDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { createOrder, register } from '../../services/httpApi.js';

vi.mock('virtual:api-impl', () => import('../../services/httpApi.js'));

// The owner's sentence, literal: the same on the returns page and in the product tab.
const SHOP_WARRANTY_KA = `ამას გარდა, ყველა პროდუქტზე მოქმედებს მაღაზიის გარანტია — ${WARRANTY_MONTHS} თვე მიწოდებიდან. საგარანტიო შემთხვევაში დაგვიკავშირდით: პროდუქტს ჩვენ ჩავიბარებთ და შეგიკეთებთ ან შეგიცვლით.`;

const PAGES = [
  ['delivery', DeliveryTerms],
  ['returns', ReturnsWarranty],
  ['privacy', Privacy],
  ['faq', Faq],
];

const TBILISI_RUSTAVI = {
  cities: [
    { name: 'თბილისი', fee: '8.00', cardOnDelivery: true },
    { name: 'რუსთავი', fee: '5.00', cardOnDelivery: true },
  ],
  freeFrom: '100.00',
};

const BATUMI = {
  cities: [{ name: 'ბათუმი', fee: '12.50', cardOnDelivery: false }],
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
  const table = screen.getByRole('table', { name: t('info.delivery.tableCaption') });
  return within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) => [...row.children].map((cell) => cell.textContent));
}

/** The FAQ entry on a forgotten password, question and answer. */
const passwordAnswer = () =>
  screen.getByRole('heading', { name: 'პაროლი დამავიწყდა, რა ვქნა?' }).closest('section');

const returnSteps = () => screen.getByRole('list', { name: t('info.returns.steps') });

const MIXED = {
  cities: [
    { name: 'თბილისი', fee: '8.00', cardOnDelivery: true },
    { name: 'ბათუმი', fee: '12.50', cardOnDelivery: false },
  ],
  freeFrom: '100.00',
};

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
        ['შეკვეთა 100 ₾-დან', 'უფასო'],
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

    expect(SHOP_FACTS.legalEntity).toBeNull();
    await mount(Privacy);
    expect(screen.queryByRole('heading', { name: 'ვინ ვართ' })).not.toBeInTheDocument();
  });

  it('appear once written into SHOP_FACTS', async () => {
    Object.assign(SHOP_FACTS, {
      legalEntity: { name: 'ი/მ ნინო ბერიძე', idCode: '01001000000', address: 'თბილისი, რუსთაველის 1' },
    });
    answer(rules());

    await mount(Privacy);
    const who = screen.getByRole('heading', { name: 'ვინ ვართ' }).closest('section');
    expect(who).toHaveTextContent('ი/მ ნინო ბერიძე');
    expect(who).toHaveTextContent('პირადი ნომერი / საიდენტიფიკაციო კოდი');
    expect(who).toHaveTextContent('01001000000');
    expect(who).toHaveTextContent('იურიდიული მისამართი');
    expect(who).toHaveTextContent('თბილისი, რუსთაველის 1');
  });

  it('is the only place a postal address can appear: no page shows the old shop address', async () => {
    answer(rules());
    for (const [, Page] of PAGES) {
      const { container, unmount } = await mount(Page);
      expect(container.textContent).not.toContain('ჭავჭავაძის გამზირი');
      unmount();
    }
  });
});

describe('payment by card on delivery', () => {
  it.each([
    ['delivery', DeliveryTerms],
    ['faq', Faq],
  ])('the %s page says cash or card when every city takes the card', async (_, Page) => {
    answer(rules());
    await mount(Page);

    expect(screen.getByText(/ნაღდი ფულით ან ბარათით/)).toBeInTheDocument();
    expect(screen.queryByText(/მალე დაემატება/)).not.toBeInTheDocument();
  });

  it.each([
    ['delivery', DeliveryTerms],
    ['faq', Faq],
  ])('the %s page lists the card cities when only some take it', async (_, Page) => {
    answer(rules(MIXED));
    await mount(Page);

    expect(
      screen.getByText(/ბარათით გადახდა შესაძლებელია მხოლოდ ამ ქალაქებში: თბილისი\./),
    ).toBeInTheDocument();
  });

  it.each([
    ['delivery', DeliveryTerms],
    ['faq', Faq],
  ])('the %s page claims no card when no city takes it', async (_, Page) => {
    answer(rules(BATUMI));
    await mount(Page);

    expect(screen.queryByText(/ბარათით/)).not.toBeInTheDocument();
    expect(screen.getByText(/ნაღდი ფულით/)).toBeInTheDocument();
  });
});

describe('the returns page', () => {
  it('sets no condition on a return, and keeps the one legal exception', async () => {
    answer(rules());
    const { container } = await mount(ReturnsWarranty);

    expect(container.textContent).not.toContain('პირობები:');
    expect(container.textContent).not.toContain('არ უნდა იყოს გამოყენებული');
    expect(screen.getByText(/მიღებიდან 14 კალენდარული დღის განმავლობაში, მიზეზის მითითების გარეშე/)).toBeInTheDocument();
    expect(screen.getByText(/ყურში ჩასადები ყურსასმენები/)).toBeInTheDocument();
    expect(screen.getByText(/დაბრუნების პირობა არ არის/)).toBeInTheDocument();
    // The exception is about the seal, not the packaging (packaging is no condition).
    const exception = screen.getByText(/ყურში ჩასადები ყურსასმენები/).textContent;
    expect(exception).toContain('ლუქი');
    expect(exception).not.toContain('შეფუთვა გახსნილია');
  });

  it('lists the four steps, the pickup one always, and a legal guarantee of 2 years', async () => {
    answer(rules());
    await mount(ReturnsWarranty);

    const steps = within(returnSteps()).getAllByRole('listitem');
    expect(steps).toHaveLength(4);
    expect(steps[1]).toHaveTextContent(
      'კურიერს ჩვენ გამოგიგზავნით — მისი მოსვლის დროს ერთად შევათანხმებთ.',
    );
    expect(steps[2]).toHaveTextContent(
      'პროდუქტი კურიერს გადაეცით შეტყობინებიდან 7 დღის განმავლობაში.',
    );
    expect(screen.getByText(/გარანტია 2 წელია მიწოდებიდან/)).toBeInTheDocument();
  });

  describe('the return courier costs what delivery to the city costs', () => {
    const feesOf = (fixture) =>
      fixture.cities.map((c) => `${c.name} — ${formatPrice(Number(c.fee))}`).join(', ');

    it.each([
      ['Tbilisi and Rustavi', TBILISI_RUSTAVI],
      ['Batumi alone', BATUMI],
    ])('lists each city with its fee from GET /delivery: %s', async (_, fixture) => {
      answer(rules(fixture));
      await mount(ReturnsWarranty);

      const expected = t('info.returns.returnShipping', { fees: feesOf(fixture) });
      expect(screen.getByText(expected)).toBeInTheDocument();
      for (const city of fixture.cities) {
        expect(expected).toContain(`${city.name} — ${formatPrice(Number(city.fee))}`);
      }
    });

    it('a different answer draws a different list', async () => {
      answer(rules(TBILISI_RUSTAVI));
      const first = await mount(ReturnsWarranty);
      expect(first.container.textContent).toContain(feesOf(TBILISI_RUSTAVI));
      expect(first.container.textContent).not.toContain('ბათუმი');
      first.unmount();

      forgetDeliveryRules();
      answer(rules(BATUMI));
      const second = await mount(ReturnsWarranty);
      expect(second.container.textContent).toContain(feesOf(BATUMI));
      expect(second.container.textContent).not.toContain('რუსთავი');
    });

    it('names no fee, and does not break, when GET /delivery fails', async () => {
      global.fetch = vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) }));
      const { container } = await mount(ReturnsWarranty);

      expect(screen.getByText(t('info.returns.returnShippingNoFees'))).toBeInTheDocument();
      expect(container.textContent).not.toContain('₾');
      expect(container.textContent).not.toContain('{{');
    });
  });

  describe('the shop gives the warranty', () => {
    it.each(['ka', 'en'])('says the term from WARRANTY_MONTHS, in %s', async (lng) => {
      await i18n.changeLanguage(lng);
      try {
        answer(rules());
        const { container } = await mount(ReturnsWarranty);

        const sentence = screen.getByText(t('info.returns.shopWarranty', { months: WARRANTY_MONTHS }));
        expect(sentence).toHaveTextContent(String(WARRANTY_MONTHS));
        expect(container.textContent).not.toContain('{{');
      } finally {
        await i18n.changeLanguage('ka');
      }
    });

    it('states the owner\'s exact sentence, in Georgian', async () => {
      answer(rules());
      await mount(ReturnsWarranty);

      expect(screen.getByText(SHOP_WARRANTY_KA)).toBeInTheDocument();
    });

    it('states the courier sentence with the delivery-price wording', async () => {
      answer(rules());
      await mount(ReturnsWarranty);

      expect(
        screen.getByText(
          /^კურიერს ჩვენ გამოგიგზავნით; მომსახურების ღირებულება უდრის თქვენს ქალაქში მიწოდების საფასურს: /,
        ),
      ).toBeInTheDocument();
    });

    it('the exclusions are the shop warranty, and leave the legal 2 years alone', async () => {
      answer(rules());
      await mount(ReturnsWarranty);

      const exclusions = screen.getByText(/^მაღაზიის გარანტია არ ვრცელდება დაზიანებაზე/);
      expect(exclusions).toHaveTextContent('ეს კანონით დადგენილ 2 წლის გარანტიას არ ზღუდავს.');
    });

    it('names no manufacturer and sends nobody to a product description', async () => {
      answer(rules());
      const { container } = await mount(ReturnsWarranty);

      expect(container.textContent).not.toMatch(/მწარმოებლ|აღწერაშია|ოფიციალ|ორიგინალ/);
    });
  });

  it('shows the withdrawal form as copyable text, with the shop email from CONTACT', async () => {
    answer(rules());
    await mount(ReturnsWarranty);

    expect(screen.getByRole('heading', { name: 'უარის განცხადების ნიმუში' })).toBeInTheDocument();
    const form = screen.getByText(/ადრესატი: VoltBox/);
    expect(form.tagName).toBe('PRE');
    expect(form).toHaveTextContent(`ადრესატი: VoltBox, ${CONTACT.email}`);
    for (const line of [
      'ვაცხადებ, რომ ვამბობ უარს შემდეგი პროდუქტის ნასყიდობაზე: …',
      'შეკვეთის ნომერი: …',
      'მიღების თარიღი: …',
      'სახელი, გვარი: …',
      'თარიღი: …',
    ]) {
      expect(form.textContent).toContain(line);
    }
    // one line each, so it pastes into an email as it reads
    expect(form.textContent.split('\n')).toHaveLength(6);
  });
});

describe('the privacy page content', () => {
  it('gives each purpose its legal basis', async () => {
    answer(rules());
    await mount(Privacy);

    const uses = screen.getByRole('heading', { name: 'რისთვის ვიყენებთ' }).closest('section');
    expect(uses).toHaveTextContent('ხელშეკრულების შესასრულებლად');
    expect(uses).toHaveTextContent('კანონით დადგენილი ვალდებულების შესასრულებლად');
    expect(uses).toHaveTextContent('კანონიერი ინტერესის საფუძველზე');
  });

  it('says the phone is required, the email optional, and what the IP is used for', async () => {
    answer(rules());
    await mount(Privacy);

    const collected = screen.getByRole('heading', { name: 'რა მონაცემებს ვაგროვებთ' }).closest('section');
    expect(collected).toHaveTextContent('ტელეფონის ნომერი შეკვეთისთვის სავალდებულოა');
    expect(collected).toHaveTextContent('ფსევდონიმიზებული');
    expect(collected).toHaveTextContent('ადმინისტრატორის IP მისამართიც ფიქსირდება');
  });

  it('names the transfers abroad, Resend only while email is on', async () => {
    answer(rules(TBILISI_RUSTAVI, false));
    const off = await mount(Privacy);
    expect(screen.getByText(/Render — .*აშშ-ისაა.*ფრანკფურტი/)).toBeInTheDocument();
    expect(screen.getByText(/Supabase — .*ევროკავშირში/)).toBeInTheDocument();
    expect(screen.queryByText(/Resend/)).not.toBeInTheDocument();
    off.unmount();

    forgetDeliveryRules();
    answer(rules(TBILISI_RUSTAVI, true));
    await mount(Privacy);
    expect(screen.getByText(/Resend — .*აშშ-ის კომპანიაა/)).toBeInTheDocument();
  });

  it('lists the rights and the State Audit Office, not the abolished service', async () => {
    answer(rules());
    const { container } = await mount(Privacy);

    const rights = screen.getByRole('heading', { name: 'თქვენი უფლებები' }).closest('section');
    for (const right of ['შესწორება', 'წაშლა', 'დამუშავების შეზღუდვა', 'შეეწინააღმდეგოთ', 'გამოიხმოთ თანხმობა']) {
      expect(rights).toHaveTextContent(right);
    }
    expect(rights).toHaveTextContent('სახელმწიფო აუდიტის სამსახურს');
    expect(rights).toHaveTextContent('სასამართლოს');
    expect(rights.textContent).not.toMatch(/მიმართოთ პერსონალურ მონაცემთა დაცვის სამსახურს/);
    expect(container.textContent).toContain('პერსონალურ მონაცემთა დაცვის სამსახურის ფუნქციები გადაიბარა');
  });
});

describe('delivery time', () => {
  it.each([
    ['delivery', DeliveryTerms, `შეკვეთის მიტანას სჭირდება ${t('shipping.etaDays')}.`],
    ['faq', Faq, `${t('shipping.etaDays')}.`],
  ])('the %s page states shipping.etaDays, as the cart does', async (_, Page, sentence) => {
    answer(rules());
    await mount(Page);

    expect(screen.getByText(sentence, { exact: false })).toBeInTheDocument();
  });
});

describe('the privacy page against the code', () => {
  /** A privacy-page section's text, by its heading. */
  async function section(heading) {
    answer(rules());
    await mount(Privacy);
    return screen.getByRole('heading', { name: heading }).closest('section').textContent;
  }

  it('names every field the Telegram notice carries, and no personal data', async () => {
    // What each `notice.<field>` in message_text() is called on the page
    const NAMED = {
      order_number: 'შეკვეთის ნომერი',
      subtotal: 'პროდუქტების ღირებულება',
      shipping: 'მიწოდების საფასური',
      total: 'ჯამი',
      item_count: 'ნივთების რაოდენობა',
      payment_method: 'გადახდის მეთოდი',
      order_id: 'ბმული შეკვეთაზე',
    };
    const source = readFileSync(
      join(process.cwd(), '..', 'backend', 'app', 'services', 'telegram.py'),
      'utf8',
    );
    const builder = source.match(/def message_text\([\s\S]*?\n\n\n/)?.[0];
    expect(builder, 'message_text moved; this test needs updating').toBeTruthy();
    const fields = [...new Set([...builder.matchAll(/notice\.(\w+)/g)].map((m) => m[1]))].filter(
      (field) => field !== 'currency',
    );

    expect(fields.sort()).toEqual(Object.keys(NAMED).sort());
    const text = await section('ვის ვუზიარებთ');

    expect(text).toContain('პერსონალური მონაცემები არ იგზავნება');
    for (const field of fields) {
      expect(NAMED[field], `notice.${field} is sent but the page does not name it`).toBeDefined();
      expect(text).toContain(NAMED[field]);
    }
  });

  it('names every field registration sends', async () => {
    const NAMED = {
      firstName: 'სახელი და გვარი',
      lastName: 'სახელი და გვარი',
      email: 'ელფოსტა',
      password: 'პაროლი',
    };
    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ user: { id: 'u1', email: 'a@b.ge' } }),
    }));
    await register({
      firstName: 'ნინო',
      lastName: 'ბერიძე',
      email: 'a@b.ge',
      password: 'secret123',
      confirmPassword: 'secret123',
    });
    const sent = Object.keys(JSON.parse(global.fetch.mock.calls[0][1].body));

    expect(sent.sort()).toEqual(Object.keys(NAMED).sort());
    const text = (await section('რა მონაცემებს ვაგროვებთ')).split('რეგისტრაციისას:')[1];

    for (const field of sent) {
      expect(NAMED[field], `registration sends ${field} but the page does not name it`).toBeDefined();
      expect(text).toContain(NAMED[field]);
    }
  });

  it('names everything the storefront keeps in the browser', async () => {
    const NAMED = {
      [STORAGE_KEYS.cart]: 'კალათის შიგთავსს',
      // A flag about the cart (a change not yet saved to the account), no data of its own
      [STORAGE_KEYS.cartUnsynced]: 'კალათის შიგთავსს',
      [STORAGE_KEYS.theme]: 'თემის არჩევანს',
      [STORAGE_KEYS.auth]: 'შესვლის სესიას',
      [STORAGE_KEYS.recentSearches]: 'ბოლო ძებნებს',
      'guest-orders:v2': 'შეკვეთის ნომერს და შემთხვევით კოდს',
    };
    // Written only by services/mockApi.js, which the http build does not contain
    const MOCK_ONLY = [STORAGE_KEYS.users, STORAGE_KEYS.orders, STORAGE_KEYS.addresses];

    global.fetch = vi.fn(async () => ({
      ok: true,
      status: 201,
      json: async () => ({ orderNumber: 'VB-20260926-00001', lookupToken: 'token-abc' }),
    }));
    // A browser that ordered before the token kept the phone here.
    localStorage.setItem('guest-orders:v1', JSON.stringify({ 'VB-20260925-00001': '555123456' }));
    await createOrder({
      items: [{ productId: 'p1', qty: 1 }],
      customer: { phone: '555123456' },
      paymentMethod: 'cash',
    });
    const kept = new Set([
      ...Object.values(STORAGE_KEYS).filter((key) => !MOCK_ONLY.includes(key)),
      ...Object.keys(localStorage),
    ]);

    expect([...kept].sort()).toEqual(Object.keys(NAMED).sort());
    const text = await section('ბრაუზერში შენახული მონაცემები');

    for (const key of kept) {
      expect(NAMED[key], `${key} is stored but the page does not name it`).toBeDefined();
      expect(text).toContain(NAMED[key]);
    }
  });
});

describe('in English', () => {
  const GEORGIAN = /[ა-ჿ]/;
  const ENGLISH_CITIES = {
    cities: [
      { name: 'Tbilisi', fee: '8.00', cardOnDelivery: true },
      { name: 'Rustavi', fee: '5.00', cardOnDelivery: true },
    ],
    freeFrom: '100.00',
  };

  beforeEach(() => i18n.changeLanguage('en'));
  afterEach(() => i18n.changeLanguage('ka'));

  describe.each([false, true])('with email %s', (email) => {
    it.each(PAGES)('the %s page has no Georgian of its own', async (_, Page) => {
      answer(rules(ENGLISH_CITIES, email));
      const { container } = await mount(Page);

      // innerHTML, so an aria-label or a caption is read as well as the text
      expect(container.textContent.length).toBeGreaterThan(0);
      expect(container.innerHTML).not.toMatch(GEORGIAN);
      expect(container.innerHTML).not.toContain('{{');
      expect(document.head.querySelector('meta[name="description"]').content).not.toMatch(GEORGIAN);
    });
  });

  it('draws the table and the Georgian city names exactly as the API sends them', async () => {
    answer(rules(TBILISI_RUSTAVI));
    await mount(DeliveryTerms);

    expect(
      screen.getByRole('table', { name: 'Delivery cost by city' }),
    ).toBeInTheDocument();
    expect(tableRows()).toEqual([
      ['თბილისი', '8 ₾'],
      ['რუსთავი', '5 ₾'],
      ['Orders from 100 ₾', 'Free'],
    ]);
  });

  it('says the delivery time as the cart does', async () => {
    answer(rules(ENGLISH_CITIES));
    await mount(DeliveryTerms);

    expect(screen.getByText('An order takes 1–3 business days to arrive.', { exact: false })).toBeInTheDocument();
  });

  it('names the links as the pages they lead to do', async () => {
    answer(rules(ENGLISH_CITIES, true));
    await mount(Faq);

    expect(screen.getByRole('link', { name: '“Returns and warranty”' })).toHaveAttribute('href', '/returns');
    expect(screen.getByRole('link', { name: '“My orders”' })).toHaveAttribute('href', '/account/orders');
    expect(screen.getByRole('link', { name: '“Forgot your password?”' })).toHaveAttribute(
      'href',
      '/forgot-password',
    );
  });

  it('puts the legal entity in the privacy page when it is written', async () => {
    Object.assign(SHOP_FACTS, {
      legalEntity: { name: 'Nino Beridze, sole proprietor', idCode: '01001000000', address: 'Tbilisi' },
    });
    answer(rules(ENGLISH_CITIES));
    await mount(Privacy);

    const who = screen.getByRole('heading', { name: 'Who we are' }).closest('section');
    expect(who).toHaveTextContent('Personal number / identification code');
    expect(who).toHaveTextContent('01001000000');
  });

  it('keeps the returns steps, the withdrawal form and the card sentence in English', async () => {
    answer(rules(ENGLISH_CITIES));
    await mount(ReturnsWarranty);

    expect(within(returnSteps()).getAllByRole('listitem')).toHaveLength(4);
    expect(screen.getByText(/^To: VoltBox, info@voltbox\.ge/)).toBeInTheDocument();
  });

  it('says cash or card on the delivery page', async () => {
    answer(rules(ENGLISH_CITIES));
    await mount(DeliveryTerms);

    expect(screen.getByText('You pay when you receive the product — in cash or by card.')).toBeInTheDocument();
  });

  it('names the seal in the legal exception on the returns page', async () => {
    answer(rules(ENGLISH_CITIES));
    await mount(ReturnsWarranty);

    expect(screen.getByText(/in-ear earphones/).textContent).toContain('seal');
  });
});

describe('storefront texts: who gives the warranty, and for how long', () => {
  const FILES = ['ka', 'en'].map((lng) => [
    lng,
    readFileSync(join(process.cwd(), 'src', 'i18n', `${lng}.json`), 'utf8'),
  ]);

  it.each(FILES)('%s.json names no official, original or manufacturer claim', (_, source) => {
    expect(source).not.toMatch(/ოფიციალ|ორიგინალ|მწარმოებლ|აღწერაშია/);
    expect(source).not.toMatch(/official|original|manufacturer|product description/i);
  });

  it.each(FILES)('%s.json holds no literal warranty term: it is {{months}}', (_, source) => {
    expect(source).not.toMatch(/12[\s-]*(თვ|month)/i);
    expect(source).toContain('{{months}}');
  });

  it('the shop warranty on the delivery tab and the returns page reads the constant', () => {
    const tab = t('deliveryInfo.warrantyText', { months: WARRANTY_MONTHS });
    expect(tab).toBe(`კანონით გარანტია 2 წელია მიწოდებიდან. ${SHOP_WARRANTY_KA}`);
    expect(tab).toContain(`${WARRANTY_MONTHS} თვე`);
    expect(t('info.returns.shopWarranty', { months: WARRANTY_MONTHS })).toBe(SHOP_WARRANTY_KA);
    expect(t('product.warranty', { months: WARRANTY_MONTHS })).toBe(`${WARRANTY_MONTHS} თვის გარანტია`);
  });
});
