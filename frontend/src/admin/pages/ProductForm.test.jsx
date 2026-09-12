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
import { RouterProvider, createMemoryRouter } from 'react-router-dom';

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

    await userEvent.type(screen.getByLabelText(/სახელი/), 'ტესტი');
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

    await userEvent.type(screen.getByLabelText(/სახელი/), 'ტესტი');
    await userEvent.type(screen.getByLabelText(/^ფასი/), '10');
    await userEvent.selectOptions(screen.getByLabelText(/კატეგორია/), 'cat-1');
    await userEvent.selectOptions(screen.getByLabelText(/ბრენდი/), 'brand-1');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    expect(await screen.findByText('ეს SKU სხვა პროდუქტს უკვე უკავია')).toBeInTheDocument();
  });

  it('never swallows a rejection whose field the form cannot show', async () => {
    // The form draws an error slot for seven fields. The API validates more
    // than seven - a negative stock threshold, an over-long spec value, too
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

    await userEvent.type(screen.getByLabelText(/სახელი/), 'ტესტი');
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

    await userEvent.type(screen.getByLabelText(/სახელი/), 'ტესტი');
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

    await userEvent.type(screen.getByLabelText(/სახელი/), 'ტესტი');
    await userEvent.type(screen.getByLabelText(/^ფასი/), '10.10');
    await userEvent.selectOptions(screen.getByLabelText(/კატეგორია/), 'cat-1');
    await userEvent.selectOptions(screen.getByLabelText(/ბრენდი/), 'brand-1');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    await waitFor(() => expect(create).toHaveBeenCalled());
    // Parsing it here is how 10.10 becomes 10.099999999999999.
    expect(create.mock.calls[0][0].price).toBe('10.10');
  });
});
