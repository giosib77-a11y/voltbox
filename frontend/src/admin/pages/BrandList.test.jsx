/**
 * Tests for BrandList's edit dialog.
 *
 * What they cover: a brand's optional English name - shown on the English
 * storefront - is read back into the dialog beside the name, and saved with it,
 * empty included, since emptying the box is how it is removed.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import BrandList from './BrandList.jsx';
import * as adminApi from '../adminApi.js';

const HOCO = {
  id: 'brand-1',
  name: 'ჰოკო',
  nameEn: 'Hoco',
  slug: 'hoko',
  country: 'ჩინეთი',
  logoUrl: null,
  productsCount: 3,
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(adminApi, 'listBrands').mockResolvedValue([HOCO]);
});

/**
 * Opens the brand's dialog - again after a save, which closes it - and waits
 * for it to take focus, which it does 30 ms after opening (Modal.jsx). Typing
 * before that loses every key after the first.
 */
async function openDialog() {
  await userEvent.click(await screen.findByRole('button', { name: 'რედაქტირება' }));
  const dialog = screen.getByRole('dialog');
  await waitFor(() => expect(dialog).toContainElement(document.activeElement));
  return screen.getByLabelText('სახელი ინგლისურად');
}

describe('BrandList English name', () => {
  it('reads the saved English name back beside the name, marked optional', async () => {
    render(<BrandList />);
    const nameEn = await openDialog();

    expect(nameEn).toHaveValue('Hoco');
    expect(screen.getByLabelText(/^სახელი\*?$/)).toHaveValue('ჰოკო');
    expect(nameEn).not.toBeRequired();
    expect(nameEn).toHaveAccessibleDescription(/არასავალდებულო/);
  });

  it('saves an edited English name, and an emptied one as empty', async () => {
    const update = vi.spyOn(adminApi, 'updateBrand').mockResolvedValue(HOCO);
    render(<BrandList />);

    const nameEn = await openDialog();
    await userEvent.clear(nameEn);
    await userEvent.type(nameEn, 'HOCO');
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));
    expect(update).toHaveBeenLastCalledWith('brand-1', expect.objectContaining({ nameEn: 'HOCO' }));

    await userEvent.clear(await openDialog());
    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));
    expect(update).toHaveBeenLastCalledWith('brand-1', expect.objectContaining({ nameEn: '' }));
  });
});
