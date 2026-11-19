/**
 * Tests for the saved-addresses page.
 *
 * They run on the real HTTP layer with only `fetch` replaced, so what is
 * checked is the whole path: the request the page sends, and what it shows
 * for the answers the API really gives - the full list after a change, and
 * the 409 `ADDRESS_LIMIT_REACHED` the 21st address gets.
 *
 * The page has no edit action and no "make default" button of its own: an
 * address is added or deleted, and the default is chosen in the add form.
 * There is nothing to test for either until the page grows them.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('virtual:api-impl', () => import('../../services/httpApi.js'));

import Addresses from './Addresses.jsx';
import { ToastProvider } from '../../context/ToastContext.jsx';
import ToastViewport from '../../components/common/Toast.jsx';
import { forgetDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { t } from '../../i18n/index.js';

// No pause between key events: the typing is incidental here, and each pause is
// a timer that stretches under CPU load.
const NO_DELAY = { delay: null };

const reply = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

const RULES = {
  cities: [
    { name: 'თბილისი', fee: '8.00' },
    { name: 'ბათუმი', fee: '12.00' },
  ],
  freeFrom: '100.00',
  currency: 'GEL',
  features: { email: false },
};

const HOME = { id: 'a1', label: 'სახლი', city: 'თბილისი', address: 'რუსთაველის 10', isDefault: true };
const WORK = { id: 'a2', label: 'სამსახური', city: 'ბათუმი', address: 'ჭავჭავაძის 5', isDefault: false };

/**
 * A fake API: GET /addresses answers `list`, the other address calls answer
 * with what `onWrite` returns (called with method, url and parsed body).
 */
function fakeApi({ list = [], onWrite = () => reply([]) } = {}) {
  global.fetch = vi.fn(async (url, init = {}) => {
    const method = init.method || 'GET';
    if (url.endsWith('/delivery')) return reply(RULES);
    if (url.endsWith('/addresses') && method === 'GET') return reply(list);
    return onWrite(method, url, init.body ? JSON.parse(init.body) : undefined);
  });
}

const writes = () =>
  global.fetch.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET');

function renderPage() {
  return render(
    <ToastProvider>
      <Addresses />
      <ToastViewport />
    </ToastProvider>,
  );
}

async function openForm(user) {
  await user.click(await screen.findByRole('button', { name: t('account.add') }));
  return screen.findByRole('dialog');
}

async function fillForm(user, dialog, { label, city, address, isDefault }) {
  const form = within(dialog);
  if (label) await user.type(form.getByLabelText(t('account.addressName')), label);
  if (city) {
    // The city list arrives with GET /delivery, a moment after the page.
    await form.findByRole('option', { name: city });
    await user.selectOptions(form.getByLabelText(t('fields.city'), { exact: false }), city);
  }
  if (address) await user.type(form.getByLabelText(t('fields.address'), { exact: false }), address);
  if (isDefault) await user.click(form.getByLabelText(t('account.makeDefault')));
}

beforeEach(() => {
  forgetDeliveryRules();
});

describe('the list', () => {
  it('shows each address with its city, and marks the default one', async () => {
    fakeApi({ list: [HOME, WORK] });
    renderPage();

    const items = await screen.findAllByRole('listitem');

    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('სახლი');
    expect(items[0]).toHaveTextContent('თბილისი, რუსთაველის 10');
    expect(within(items[0]).getByText(t('account.default'))).toBeInTheDocument();
    expect(items[1]).toHaveTextContent('ბათუმი, ჭავჭავაძის 5');
    expect(within(items[1]).queryByText(t('account.default'))).not.toBeInTheDocument();
  });

  it('shows the empty state, which also opens the add form', async () => {
    fakeApi({ list: [] });
    const user = userEvent.setup(NO_DELAY);
    renderPage();

    expect(await screen.findByText(t('account.noAddresses'))).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: t('account.addAddress') }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });

  it('shows an error with a retry when the list cannot be loaded, and loads on retry', async () => {
    let failing = true;
    global.fetch = vi.fn(async (url) => {
      if (url.endsWith('/delivery')) return reply(RULES);
      return failing ? reply({ error: { code: 'INTERNAL', message: 'boom' } }, 500) : reply([HOME]);
    });
    const user = userEvent.setup(NO_DELAY);
    renderPage();

    const retry = await screen.findByRole('button', { name: t('common.retry') });
    expect(screen.queryByRole('list')).not.toBeInTheDocument();

    failing = false;
    await user.click(retry);

    expect(await screen.findByText('თბილისი, რუსთაველის 10')).toBeInTheDocument();
  });
});

describe('adding an address', () => {
  it('sends the form, shows the list the server answers with, and closes the form', async () => {
    fakeApi({ list: [], onWrite: () => reply([WORK], 201) });
    const user = userEvent.setup(NO_DELAY);
    renderPage();
    const dialog = await openForm(user);

    await fillForm(user, dialog, { label: 'სამსახური', city: 'ბათუმი', address: 'ჭავჭავაძის 5' });
    await user.click(within(dialog).getByRole('button', { name: t('common.save') }));

    expect(await screen.findByText('ბათუმი, ჭავჭავაძის 5')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByText(t('account.addressSaved'))).toBeInTheDocument();

    expect(writes()).toHaveLength(1);
    const [url, init] = writes()[0];
    expect(url).toMatch(/\/addresses$/);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({
      label: 'სამსახური',
      city: 'ბათუმი',
      address: 'ჭავჭავაძის 5',
      isDefault: false,
    });
  });

  it('sends isDefault when the box is ticked, and shows the new default', async () => {
    fakeApi({
      list: [HOME],
      onWrite: () => reply([{ ...HOME, isDefault: false }, { ...WORK, isDefault: true }], 201),
    });
    const user = userEvent.setup(NO_DELAY);
    renderPage();
    const dialog = await openForm(user);

    await fillForm(user, dialog, { city: 'ბათუმი', address: 'ჭავჭავაძის 5', isDefault: true });
    await user.click(within(dialog).getByRole('button', { name: t('common.save') }));

    const items = await screen.findAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(JSON.parse(writes()[0][1].body)).toMatchObject({ isDefault: true });
    expect(within(items[0]).queryByText(t('account.default'))).not.toBeInTheDocument();
    expect(within(items[1]).getByText(t('account.default'))).toBeInTheDocument();
  });

  it('does not send an empty form, and says what is missing', async () => {
    fakeApi({ list: [] });
    const user = userEvent.setup(NO_DELAY);
    renderPage();
    const dialog = await openForm(user);

    await user.click(within(dialog).getByRole('button', { name: t('common.save') }));

    expect(within(dialog).getByText(t('validation.city'), { selector: 'p' })).toBeInTheDocument();
    expect(within(dialog).getByText(t('validation.address'))).toBeInTheDocument();
    expect(writes()).toHaveLength(0);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('refuses an address that is too short', async () => {
    fakeApi({ list: [] });
    const user = userEvent.setup(NO_DELAY);
    renderPage();
    const dialog = await openForm(user);

    await fillForm(user, dialog, { city: 'თბილისი', address: 'abc' });
    await user.click(within(dialog).getByRole('button', { name: t('common.save') }));

    expect(within(dialog).getByText(t('validation.addressShort'))).toBeInTheDocument();
    expect(writes()).toHaveLength(0);
  });

  it('shows the server limit text, keeps the form open and the list unchanged', async () => {
    fakeApi({
      list: [HOME],
      onWrite: () =>
        reply(
          { error: { code: 'ADDRESS_LIMIT_REACHED', message: 'Address limit reached', details: null } },
          409,
        ),
    });
    const user = userEvent.setup(NO_DELAY);
    renderPage();
    const dialog = await openForm(user);

    await fillForm(user, dialog, { city: 'ბათუმი', address: 'ჭავჭავაძის 5' });
    await user.click(within(dialog).getByRole('button', { name: t('common.save') }));

    expect(await screen.findByText(t('apiErrors.ADDRESS_LIMIT_REACHED'))).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.queryByText(t('account.addressSaved'))).not.toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
  });

  it('shows a toast, not a crash, when the network is down', async () => {
    global.fetch = vi.fn(async (url, init = {}) => {
      if (url.endsWith('/delivery')) return reply(RULES);
      if ((init.method || 'GET') === 'GET') return reply([]);
      throw new TypeError('Failed to fetch');
    });
    const user = userEvent.setup(NO_DELAY);
    renderPage();
    const dialog = await openForm(user);

    await fillForm(user, dialog, { city: 'ბათუმი', address: 'ჭავჭავაძის 5' });
    await user.click(within(dialog).getByRole('button', { name: t('common.save') }));

    expect(await screen.findByText(t('apiErrors.network'))).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});

describe('deleting an address', () => {
  it('sends DELETE for that address and shows the list the server answers with', async () => {
    fakeApi({ list: [HOME, WORK], onWrite: () => reply([HOME]) });
    const user = userEvent.setup(NO_DELAY);
    renderPage();
    const items = await screen.findAllByRole('listitem');

    await user.click(within(items[1]).getByRole('button', { name: t('account.deleteAddress') }));

    expect(await screen.findByText(t('account.addressDeleted'))).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    expect(screen.queryByText('ბათუმი, ჭავჭავაძის 5')).not.toBeInTheDocument();
    const [url, init] = writes()[0];
    expect(url).toMatch(/\/addresses\/a2$/);
    expect(init.method).toBe('DELETE');
  });

  it('keeps the address and says so when the delete fails', async () => {
    fakeApi({
      list: [HOME],
      onWrite: () => reply({ error: { code: 'SOME_UNMAPPED_CODE', message: 'Address not found' } }, 404),
    });
    const user = userEvent.setup(NO_DELAY);
    renderPage();
    const items = await screen.findAllByRole('listitem');

    await user.click(within(items[0]).getByRole('button', { name: t('account.deleteAddress') }));

    expect(await screen.findByText('Address not found')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    expect(screen.queryByText(t('account.addressDeleted'))).not.toBeInTheDocument();
  });
});
