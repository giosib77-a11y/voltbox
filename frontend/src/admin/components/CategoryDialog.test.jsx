/**
 * Tests for CategoryDialog's filters editor.
 *
 * What they cover: `match` belongs to a toggle and to nothing else - the API
 * rejects it elsewhere and FilterSidebar ignores it - so the field appears only
 * for a toggle and is stripped from everything else on save. Also that each
 * control carries a visible label: four boxes in a row with no labels is not a
 * form anyone can fill in correctly.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import CategoryDialog from './CategoryDialog.jsx';
import * as adminApi from '../adminApi.js';

const CATEGORY = {
  id: 'cat-1',
  name: 'ტელეფონები',
  slug: 'phones',
  shortName: 'ტელეფონები',
  description: '',
  icon: 'Smartphone',
  parentId: null,
  position: 0,
  filters: [
    { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
    { key: 'specs.fastCharge', label: 'სწრაფი დატენვა', type: 'toggle', match: true },
  ],
};

function renderDialog(category = null) {
  return render(
    <CategoryDialog
      category={category}
      categories={[]}
      onClose={() => {}}
      onSaved={() => {}}
    />,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('CategoryDialog filters', () => {
  it('says what an empty filter list means rather than showing nothing', () => {
    renderDialog();

    expect(screen.getByText(/გვერდითა პანელი ცარიელი დარჩება/)).toBeInTheDocument();
  });

  it('names every control, and heads the columns once', async () => {
    renderDialog();

    await userEvent.click(screen.getByRole('button', { name: /ფილტრის დამატება/ }));

    // Column headings carry the names on screen; the controls carry them for
    // assistive technology. Both have to be there.
    expect(screen.getByLabelText('გასაღები')).toBeInTheDocument();
    expect(screen.getByLabelText('ლეიბლი')).toBeInTheDocument();
    expect(screen.getByLabelText('ტიპი')).toBeInTheDocument();

    // One heading row, however many filters - not a title per row.
    await userEvent.click(screen.getByRole('button', { name: /ფილტრის დამატება/ }));
    expect(screen.getAllByLabelText('გასაღები')).toHaveLength(2);
    expect(screen.getAllByText('ტიპი')).toHaveLength(1);
  });

  it('shows the match field only for a toggle', async () => {
    renderDialog();
    await userEvent.click(screen.getByRole('button', { name: /ფილტრის დამატება/ }));

    // A new filter defaults to checkbox, where `match` means nothing.
    expect(screen.queryByLabelText('ჩართვის მნიშვნელობა')).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText('ტიპი'), 'toggle');

    expect(screen.getByLabelText('ჩართვის მნიშვნელობა')).toBeInTheDocument();
  });

  it('keeps the actions out of the scrolling area but still submitting', async () => {
    // A long category scrolled the save button off the screen entirely.
    const update = vi.spyOn(adminApi, 'updateCategory').mockResolvedValue(CATEGORY);
    renderDialog(CATEGORY);

    const save = screen.getByRole('button', { name: 'შენახვა' });
    // The modal footer sits outside the overflow-y-auto body, so the button
    // must not be a descendant of the form...
    expect(document.getElementById('admin-category-form').contains(save)).toBe(false);

    // ...and the form= association is what still makes it submit.
    await userEvent.click(save);

    expect(update).toHaveBeenCalledTimes(1);
  });

  it('sends match for the toggle and strips it from the rest', async () => {
    const update = vi.spyOn(adminApi, 'updateCategory').mockResolvedValue(CATEGORY);
    renderDialog(CATEGORY);

    await userEvent.click(screen.getByRole('button', { name: 'შენახვა' }));

    expect(update).toHaveBeenCalledTimes(1);
    const [, payload] = update.mock.calls[0];
    expect(payload.filters).toEqual([
      { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
      // The literal string has to become a boolean: `true` is a real value in
      // live specs, and "true" would never match it.
      { key: 'specs.fastCharge', label: 'სწრაფი დატენვა', type: 'toggle', match: true },
    ]);
  });
});
