/**
 * Tests for the catalogue pagination.
 *
 * It is a controlled component: it draws the pages around the current one,
 * marks the current page, and reports a click through `onChange`. The page
 * number it reports is what the catalogue puts in the address.
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import Pagination from './Pagination.jsx';
import { t } from '../../i18n/index.js';

const previous = () => screen.getByRole('button', { name: t('pagination.previous') });
const next = () => screen.getByRole('button', { name: t('pagination.next') });

/** The numbered buttons and gaps, in order, as text: ['1', '…', '4', ...]. */
function drawn() {
  const nav = screen.getByRole('navigation', { name: t('pagination.label') });
  return Array.from(nav.children)
    .map((node) => node.textContent)
    .filter(Boolean);
}

describe('what is drawn', () => {
  it('draws nothing for a single page, or none', () => {
    const { container, rerender } = render(<Pagination page={1} totalPages={1} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();

    rerender(<Pagination page={1} totalPages={0} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('draws every page when there are seven or fewer', () => {
    render(<Pagination page={3} totalPages={7} onChange={() => {}} />);

    expect(drawn()).toEqual(['1', '2', '3', '4', '5', '6', '7']);
  });

  it('marks the current page, and only it, with aria-current', () => {
    render(<Pagination page={3} totalPages={5} onChange={() => {}} />);

    const current = screen.getAllByRole('button').filter((b) => b.getAttribute('aria-current') === 'page');
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent('3');
  });

  it('collapses the far end into a gap near the start', () => {
    render(<Pagination page={1} totalPages={20} onChange={() => {}} />);

    expect(drawn()).toEqual(['1', '2', '…', '20']);
  });

  it('collapses both sides in the middle', () => {
    render(<Pagination page={10} totalPages={20} onChange={() => {}} />);

    expect(drawn()).toEqual(['1', '…', '9', '10', '11', '…', '20']);
  });

  it('collapses the start into a gap near the end', () => {
    render(<Pagination page={20} totalPages={20} onChange={() => {}} />);

    expect(drawn()).toEqual(['1', '…', '19', '20']);
  });

  it('does not draw a gap where the neighbours already touch the ends', () => {
    render(<Pagination page={3} totalPages={20} onChange={() => {}} />);

    expect(drawn()).toEqual(['1', '2', '3', '4', '…', '20']);
  });

  it('hides the gaps from assistive technology', () => {
    render(<Pagination page={10} totalPages={20} onChange={() => {}} />);

    const nav = screen.getByRole('navigation', { name: t('pagination.label') });
    const gaps = nav.querySelectorAll('span');
    expect(gaps).toHaveLength(2);
    gaps.forEach((gap) => expect(gap).toHaveAttribute('aria-hidden', 'true'));
  });
});

describe('the arrows', () => {
  it('disables previous on the first page and keeps next enabled', () => {
    render(<Pagination page={1} totalPages={5} onChange={() => {}} />);

    expect(previous()).toBeDisabled();
    expect(next()).toBeEnabled();
  });

  it('disables next on the last page and keeps previous enabled', () => {
    render(<Pagination page={5} totalPages={5} onChange={() => {}} />);

    expect(next()).toBeDisabled();
    expect(previous()).toBeEnabled();
  });

  it('enables both in the middle', () => {
    render(<Pagination page={3} totalPages={5} onChange={() => {}} />);

    expect(previous()).toBeEnabled();
    expect(next()).toBeEnabled();
  });
});

describe('what a click reports', () => {
  it('reports the page number that was clicked', async () => {
    const onChange = vi.fn();
    render(<Pagination page={1} totalPages={5} onChange={onChange} />);

    await userEvent.click(within(screen.getByRole('navigation')).getByRole('button', { name: '4' }));

    expect(onChange).toHaveBeenCalledExactlyOnceWith(4);
  });

  it('reports the previous and the next page from the arrows', async () => {
    const onChange = vi.fn();
    render(<Pagination page={3} totalPages={5} onChange={onChange} />);

    await userEvent.click(previous());
    await userEvent.click(next());

    expect(onChange.mock.calls).toEqual([[2], [4]]);
  });

  it('reports nothing from a disabled arrow', async () => {
    const onChange = vi.fn();
    render(<Pagination page={1} totalPages={5} onChange={onChange} />);

    await userEvent.click(previous());

    expect(onChange).not.toHaveBeenCalled();
  });

  it('can be driven from the keyboard', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Pagination page={1} totalPages={5} onChange={onChange} />);

    next().focus();
    await user.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledExactlyOnceWith(2);
  });
});
