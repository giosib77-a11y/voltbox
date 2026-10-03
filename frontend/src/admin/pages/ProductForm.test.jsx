/**
 * Tests for ProductForm.
 *
 * What they cover: local validation before a request is made, and that the
 * server's answers land on the field that caused them - a 409 for a duplicate
 * SKU has to appear next to the SKU box, not as a banner the author has to
 * decode.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider, createMemoryRouter } from 'react-router';

import ProductForm from './ProductForm.jsx';
import * as adminApi from '../adminApi.js';

const CATEGORIES = [
  {
    id: 'cat-1',
    name: 'ტელეფონები',
    filters: [
      { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
      { key: 'specs.ram', label: 'ოპერატიული მეხსიერება', type: 'checkbox' },
    ],
  },
];
const BRANDS = [{ id: 'brand-1', name: 'Apple' }];

/** The Georgian name's box - not "სახელი ინგლისურად" beside it. `*` marks it required. */
const GEORGIAN_NAME = /^სახელი\*?$/;

/**
 * A data router, not MemoryRouter: ProductForm uses useBlocker to warn about
 * unsaved changes, and that hook only exists inside a data router.
 */
function renderForm() {
  const router = createMemoryRouter(
    [
      { path: '/admin/products/new', element: <ProductForm /> },
      { path: '/admin/products/:id', element: <div>შენახულია</div> },
    ],
    { initialEntries: ['/admin/products/new'] },
  );
  return render(<RouterProvider router={router} />);
}

beforeEach(() => {
  vi.spyOn(adminApi, 'listCategories').mockResolvedValue(CATEGORIES);
  vi.spyOn(adminApi, 'listBrands').mockResolvedValue(BRANDS);
});

describe('ProductForm validation', () => {
  it('does not call the API when required fields are empty', async () => {
    const create = vi.spyOn(adminApi, 'createProduct');
    renderForm();

    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    expect(await screen.findByText('სახელი სავალდებულოა')).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it('rejects an old price that is not above the price', async () => {
    renderForm();
    await screen.findByLabelText(/კატეგორია/);

    await userEvent.type(screen.getByLabelText(GEORGIAN_NAME), 'ტესტი');
    await userEvent.type(screen.getByLabelText(/^ფასი/), '100');
    await userEvent.type(screen.getByLabelText(/ძველი ფასი/), '90');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    expect(
      await screen.findByText('ძველი ფასი მიმდინარეზე მაღალი უნდა იყოს'),
    ).toBeInTheDocument();
  });

  it('says what is missing when the shop has no categories or brands yet', async () => {
    // The state of every new shop. Both selects are required, so without this
    // the first product anybody adds is a form that refuses to save beside two
    // empty dropdowns.
    adminApi.listCategories.mockResolvedValue([]);
    adminApi.listBrands.mockResolvedValue([]);
    renderForm();

    expect(await screen.findByRole('link', { name: 'კატეგორია' })).toHaveAttribute(
      'href',
      '/admin/categories',
    );
    expect(screen.getByRole('link', { name: 'ბრენდი' })).toHaveAttribute('href', '/admin/brands');
  });

  it('says nothing of the sort once both exist', async () => {
    renderForm();
    await screen.findByLabelText(/კატეგორია/);

    expect(screen.queryByRole('link', { name: 'კატეგორია' })).not.toBeInTheDocument();
  });

  it('shows the category filter spec keys once a category is chosen', async () => {
    renderForm();
    const categorySelect = await screen.findByLabelText(/კატეგორია/);

    await userEvent.selectOptions(categorySelect, 'cat-1');

    // The whole point: the admin sees the exact key the filter expects, so
    // "RAM" cannot be typed where the filter says "ram".
    expect(await screen.findByLabelText(/ოპერატიული მეხსიერება/)).toBeInTheDocument();
    // `brand` is a filter but not a spec, so it must not appear here.
    expect(screen.queryByText('brand')).not.toBeInTheDocument();
  });
});

describe('ProductForm server errors', () => {
  it('puts a duplicate SKU conflict on the SKU field', async () => {
    const conflict = Object.assign(new Error('SKU already used'), {
      status: 409,
      details: { code: 'SKU_TAKEN' },
    });
    vi.spyOn(adminApi, 'createProduct').mockRejectedValue(conflict);

    renderForm();
    await screen.findByLabelText(/კატეგორია/);

    await userEvent.type(screen.getByLabelText(GEORGIAN_NAME), 'ტესტი');
    await userEvent.type(screen.getByLabelText(/^ფასი/), '10');
    await userEvent.selectOptions(screen.getByLabelText(/კატეგორია/), 'cat-1');
    await userEvent.selectOptions(screen.getByLabelText(/ბრენდი/), 'brand-1');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    expect(await screen.findByText('ეს SKU სხვა პროდუქტს უკვე უკავია')).toBeInTheDocument();
  });

  it('never swallows a rejection whose field the form cannot show', async () => {
    // The form draws an error slot for eight fields. The API validates more
    // than eight - a negative stock threshold, an over-long spec value, too
    // many tags. Mapping one of those onto `errors.lowStockThreshold` puts the
    // message somewhere nothing renders, and if that also counted as "handled"
    // the save would fail in silence: no message, no navigation, nothing.
    const rejected = Object.assign(new Error('Invalid request'), {
      status: 400,
      details: {
        code: 'VALIDATION_ERROR',
        details: [
          { field: 'lowStockThreshold', message: 'Input should be greater than or equal to 0' },
        ],
      },
    });
    vi.spyOn(adminApi, 'createProduct').mockRejectedValue(rejected);

    renderForm();
    await screen.findByLabelText(/კატეგორია/);

    await userEvent.type(screen.getByLabelText(GEORGIAN_NAME), 'ტესტი');
    await userEvent.type(screen.getByLabelText(/^ფასი/), '10');
    await userEvent.selectOptions(screen.getByLabelText(/კატეგორია/), 'cat-1');
    await userEvent.selectOptions(screen.getByLabelText(/ბრენდი/), 'brand-1');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid request');
  });

  it('still shows only the field message when the form can render it', async () => {
    // The banner is the fallback, not a second copy: a message that lands on
    // its own field must not also appear at the top of the form.
    const rejected = Object.assign(new Error('Invalid request'), {
      status: 400,
      details: {
        code: 'VALIDATION_ERROR',
        details: [{ field: 'price', message: 'Input should be greater than or equal to 0' }],
      },
    });
    vi.spyOn(adminApi, 'createProduct').mockRejectedValue(rejected);

    renderForm();
    await screen.findByLabelText(/კატეგორია/);

    await userEvent.type(screen.getByLabelText(GEORGIAN_NAME), 'ტესტი');
    await userEvent.type(screen.getByLabelText(/^ფასი/), '10');
    await userEvent.selectOptions(screen.getByLabelText(/კატეგორია/), 'cat-1');
    await userEvent.selectOptions(screen.getByLabelText(/ბრენდი/), 'brand-1');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    expect(
      await screen.findByText('Input should be greater than or equal to 0'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('sends money exactly as typed, never parsed into a float', async () => {
    // Rejects on purpose: a resolved create navigates, and React Router's data
    // router then builds a Request whose jsdom AbortSignal undici refuses. The
    // payload is what this test is about, and it is captured either way.
    const create = vi
      .spyOn(adminApi, 'createProduct')
      .mockRejectedValue(Object.assign(new Error('offline'), { status: 0 }));

    renderForm();
    await screen.findByLabelText(/კატეგორია/);

    await userEvent.type(screen.getByLabelText(GEORGIAN_NAME), 'ტესტი');
    await userEvent.type(screen.getByLabelText(/^ფასი/), '10.10');
    await userEvent.selectOptions(screen.getByLabelText(/კატეგორია/), 'cat-1');
    await userEvent.selectOptions(screen.getByLabelText(/ბრენდი/), 'brand-1');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    await waitFor(() => expect(create).toHaveBeenCalled());
    // Parsing it here is how 10.10 becomes 10.099999999999999.
    expect(create.mock.calls[0][0].price).toBe('10.10');
  });
});

describe('ProductForm English name and description', () => {
  const SAVED = {
    id: 'p-1',
    name: 'პორტატული დინამიკი',
    nameEn: 'Portable Speaker',
    slug: 'portatuli-dinamiki',
    sku: null,
    categoryId: 'cat-1',
    brandId: 'brand-1',
    price: '199.00',
    oldPrice: null,
    shortDescription: '',
    description: 'წყალგამძლე.',
    descriptionEn: 'Waterproof.',
    specs: {},
    tags: [],
    lowStockThreshold: 3,
    stock: 4,
    isActive: true,
    isFeatured: false,
    isNew: false,
    archivedAt: null,
    images: [],
    rating: 0,
    reviewsCount: 0,
  };

  function renderEdit() {
    const router = createMemoryRouter(
      [{ path: '/admin/products/:id', element: <ProductForm /> }],
      { initialEntries: ['/admin/products/p-1'] },
    );
    return render(<RouterProvider router={router} />);
  }

  it('sits beside the Georgian, says it is optional, and does not block a save', async () => {
    renderForm();
    await screen.findByLabelText(/კატეგორია/);

    const nameEn = screen.getByLabelText('სახელი ინგლისურად');
    const descriptionEn = screen.getByLabelText('სრული აღწერა ინგლისურად');
    for (const field of [nameEn, descriptionEn]) {
      expect(field).not.toBeRequired();
      expect(field).toHaveAccessibleDescription(/არასავალდებულო/);
      expect(field).toHaveAttribute('lang', 'en');
    }

    // Georgian only, English left empty: the form still saves.
    const create = vi
      .spyOn(adminApi, 'createProduct')
      .mockRejectedValue(Object.assign(new Error('offline'), { status: 0 }));
    await userEvent.type(screen.getByLabelText(GEORGIAN_NAME), 'დინამიკი');
    await userEvent.type(screen.getByLabelText(/^ფასი/), '10');
    await userEvent.selectOptions(screen.getByLabelText(/კატეგორია/), 'cat-1');
    await userEvent.selectOptions(screen.getByLabelText(/ბრენდი/), 'brand-1');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).toMatchObject({ nameEn: '', descriptionEn: '' });
  });

  it('saves both names and both descriptions on create', async () => {
    // Rejected for the same reason as the money test above: the payload is the
    // point, and a resolved create would navigate.
    const create = vi
      .spyOn(adminApi, 'createProduct')
      .mockRejectedValue(Object.assign(new Error('offline'), { status: 0 }));
    renderForm();
    await screen.findByLabelText(/კატეგორია/);

    await userEvent.type(screen.getByLabelText(GEORGIAN_NAME), 'პორტატული დინამიკი');
    await userEvent.type(screen.getByLabelText('სახელი ინგლისურად'), '  Portable Speaker ');
    await userEvent.type(screen.getByLabelText('სრული აღწერა'), 'წყალგამძლე.');
    await userEvent.type(screen.getByLabelText('სრული აღწერა ინგლისურად'), 'Waterproof.');
    await userEvent.type(screen.getByLabelText(/^ფასი/), '199');
    await userEvent.selectOptions(screen.getByLabelText(/კატეგორია/), 'cat-1');
    await userEvent.selectOptions(screen.getByLabelText(/ბრენდი/), 'brand-1');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).toMatchObject({
      name: 'პორტატული დინამიკი',
      nameEn: 'Portable Speaker',
      description: 'წყალგამძლე.',
      descriptionEn: 'Waterproof.',
    });
  });

  it('reloads both, and saves an emptied English name as empty rather than keeping it', async () => {
    vi.spyOn(adminApi, 'getProduct').mockResolvedValue(SAVED);
    const update = vi
      .spyOn(adminApi, 'updateProduct')
      .mockImplementation(async (id, patch) => ({ ...SAVED, ...patch }));
    renderEdit();

    const nameEn = await screen.findByLabelText('სახელი ინგლისურად');
    expect(screen.getByLabelText(GEORGIAN_NAME)).toHaveValue('პორტატული დინამიკი');
    expect(nameEn).toHaveValue('Portable Speaker');
    expect(screen.getByLabelText('სრული აღწერა')).toHaveValue('წყალგამძლე.');
    expect(screen.getByLabelText('სრული აღწერა ინგლისურად')).toHaveValue('Waterproof.');

    await userEvent.clear(nameEn);
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    await waitFor(() => expect(update).toHaveBeenCalled());
    expect(update.mock.calls[0][0]).toBe('p-1');
    expect(update.mock.calls[0][1]).toMatchObject({ nameEn: '', descriptionEn: 'Waterproof.' });
    // What the server answered is what the form shows next.
    await waitFor(() => expect(screen.getByLabelText('სახელი ინგლისურად')).toHaveValue(''));
    expect(screen.getByLabelText('სრული აღწერა ინგლისურად')).toHaveValue('Waterproof.');
  });
});
