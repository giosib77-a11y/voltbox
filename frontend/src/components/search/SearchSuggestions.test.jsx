/**
 * Tests for the search drop-down.
 *
 * It is a presentational component: SearchBar owns the query, the results and
 * the keyboard, and passes them in. What is checked here is what each mode
 * draws and which callback each click calls.
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import SearchSuggestions from './SearchSuggestions.jsx';
import { formatPrice } from '../../utils/format.js';
import { t } from '../../i18n/index.js';

const PHONE = { id: 'p1', name: 'iPhone 15', brand: 'Apple', price: 2499, images: ['/a.jpg'] };
const CASE = { id: 'p2', name: 'iPhone case', brand: 'Spigen', price: 59, images: [] };

describe('results mode', () => {
  it('lists each product with its brand and price, then the view-all row', () => {
    render(<SearchSuggestions results={[PHONE, CASE]} query="iph" listId="l" />);

    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(3);
    expect(options[0]).toHaveTextContent('iPhone 15');
    expect(options[0]).toHaveTextContent('Apple');
    expect(options[0]).toHaveTextContent(formatPrice(2499));
    expect(options[1]).toHaveTextContent('iPhone case');
    expect(options[2]).toHaveTextContent(t('common.viewAllResults'));
  });

  it('says nothing was found for the query when there are no results', () => {
    render(<SearchSuggestions results={[]} query="zzzz" />);

    expect(screen.getByText(t('search.noResultsFor', { query: 'zzzz' }))).toBeInTheDocument();
    expect(screen.queryByRole('option')).not.toBeInTheDocument();
  });

  it('shows placeholders, not "nothing found", while the answer is on its way', () => {
    const { container } = render(<SearchSuggestions results={[]} query="iph" loading />);

    // Three placeholder rows, each an image block and two text lines.
    expect(container.querySelectorAll('li')).toHaveLength(3);
    expect(container.querySelectorAll('.animate-shimmer')).toHaveLength(9);
    expect(screen.queryByText(t('search.noResultsFor', { query: 'iph' }))).not.toBeInTheDocument();
    expect(screen.queryByRole('option')).not.toBeInTheDocument();
  });

  it('writes a query as text, never as markup', () => {
    render(<SearchSuggestions results={[]} query={'<img src=x onerror=alert(1)>'} />);

    expect(document.querySelector('img')).toBeNull();
    expect(screen.getByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
  });

  it('calls onSelect with the product that was clicked', async () => {
    const onSelect = vi.fn();
    render(<SearchSuggestions results={[PHONE, CASE]} query="iph" onSelect={onSelect} />);

    await userEvent.click(screen.getByRole('option', { name: /iPhone case/ }));

    expect(onSelect).toHaveBeenCalledExactlyOnceWith(CASE);
  });

  it('calls onViewAll from the last row', async () => {
    const onViewAll = vi.fn();
    render(<SearchSuggestions results={[PHONE]} query="iph" onViewAll={onViewAll} />);

    await userEvent.click(screen.getByRole('option', { name: t('common.viewAllResults') }));

    expect(onViewAll).toHaveBeenCalledTimes(1);
  });

  it('marks the active option, and gives only it the id the input points to', () => {
    render(<SearchSuggestions results={[PHONE, CASE]} query="iph" activeIndex={1} optionId="active" />);

    const options = screen.getAllByRole('option');
    expect(options.map((o) => o.getAttribute('aria-selected'))).toEqual(['false', 'true', 'false']);
    expect(options[1]).toHaveAttribute('id', 'active');
    expect(document.querySelectorAll('#active')).toHaveLength(1);
  });

  it('marks the view-all row active when the index is past the results', () => {
    render(<SearchSuggestions results={[PHONE]} query="iph" activeIndex={1} optionId="active" />);

    expect(screen.getByRole('option', { name: t('common.viewAllResults') })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });
});

describe('recent mode', () => {
  const recent = ['iphone', 'samsung'];

  it('lists the recent searches', () => {
    render(<SearchSuggestions mode="recent" recent={recent} />);

    expect(screen.getByText(t('common.recentSearches'))).toBeInTheDocument();
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(recent);
  });

  it('searches again from a recent term', async () => {
    const onSelectRecent = vi.fn();
    render(<SearchSuggestions mode="recent" recent={recent} onSelectRecent={onSelectRecent} />);

    await userEvent.click(screen.getByRole('option', { name: 'samsung' }));

    expect(onSelectRecent).toHaveBeenCalledExactlyOnceWith('samsung');
  });

  it('forgets one term without searching it', async () => {
    const onForgetRecent = vi.fn();
    const onSelectRecent = vi.fn();
    render(
      <SearchSuggestions
        mode="recent"
        recent={recent}
        onForgetRecent={onForgetRecent}
        onSelectRecent={onSelectRecent}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: t('search.forget', { term: 'iphone' }) }));

    expect(onForgetRecent).toHaveBeenCalledExactlyOnceWith('iphone');
    expect(onSelectRecent).not.toHaveBeenCalled();
  });

  it('clears the whole history', async () => {
    const onClearRecent = vi.fn();
    render(<SearchSuggestions mode="recent" recent={recent} onClearRecent={onClearRecent} />);

    await userEvent.click(screen.getByRole('button', { name: t('common.clearAll') }));

    expect(onClearRecent).toHaveBeenCalledTimes(1);
  });
});
