/**
 * Smoke tests for CategoryList.
 *
 * What they cover: the category tree with a child under its parent, the empty
 * list, and the error state with a retry that reloads.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import CategoryList from './CategoryList.jsx';
import * as adminApi from '../adminApi.js';
import { t } from '../../i18n/index.js';
import { ApiError } from '../../services/errors.js';

const ROOT = {
  id: 'cat-1',
  parentId: null,
  name: 'კაბელები',
  slug: 'cables',
  filters: [{ key: 'length' }],
  productsCount: 4,
  position: 1,
};
const CHILD = {
  id: 'cat-2',
  parentId: 'cat-1',
  name: 'USB-C',
  slug: 'usb-c',
  filters: [],
  productsCount: 2,
  position: 1,
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('CategoryList', () => {
  it('lists the tree with the child after its parent', async () => {
    vi.spyOn(adminApi, 'listCategories').mockResolvedValue([CHILD, ROOT]);
    render(<CategoryList />);

    expect(await screen.findByText('კაბელები')).toBeInTheDocument();
    const names = screen.getAllByRole('row').map((row) => row.textContent);
    expect(names[1]).toContain('კაბელები');
    expect(names[2]).toContain('USB-C');
    expect(screen.getByText('1 ფილტრი')).toBeInTheDocument();
  });

  it('shows the empty state when there are no categories', async () => {
    vi.spyOn(adminApi, 'listCategories').mockResolvedValue([]);
    render(<CategoryList />);

    expect(await screen.findByText('კატეგორია არ არის')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ახალი კატეგორია/ })).toBeInTheDocument();
  });

  it('shows the error state and loads again on retry', async () => {
    const list = vi
      .spyOn(adminApi, 'listCategories')
      .mockRejectedValueOnce(new ApiError('სერვერი მიუწვდომელია', 500))
      .mockResolvedValue([ROOT]);
    render(<CategoryList />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('კატეგორიები ვერ ჩაიტვირთა');
    expect(alert).toHaveTextContent('სერვერი მიუწვდომელია');

    await userEvent.click(screen.getByRole('button', { name: t('common.retry') }));
    expect(await screen.findByText('კაბელები')).toBeInTheDocument();
    expect(list).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
