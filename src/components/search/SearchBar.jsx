import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import SearchSuggestions from './SearchSuggestions.jsx';
import { useDebounce } from '../../hooks/useDebounce.js';
import { useRecentSearches } from '../../hooks/useRecentSearches.js';
import * as api from '../../services/api.js';
import { QUERY_KEYS, TEXT } from '../../constants/index.js';

/**
 * ძებნის ველი autocomplete-ით.
 *
 * · debounce 300ms
 * · ცარიელ ველზე — ბოლო ძებნები (localStorage), 2+ სიმბოლოზე — top-5 შედეგი
 * · კლავიატურა: ↑ ↓ Enter Esc (ორივე რეჟიმში)
 */

const SUGGESTION_LIMIT = 5;
const MIN_QUERY = 2;

export default function SearchBar({ defaultValue = '', autoFocus = false, onSubmitted, className = '' }) {
  const navigate = useNavigate();
  const [value, setValue] = useState(defaultValue);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const { recent, remember, forget, clear, sync } = useRecentSearches();

  const wrapperRef = useRef(null);
  const inputRef = useRef(null);
  const debounced = useDebounce(value.trim(), 300);

  const listId = useId();
  const optionId = `${listId}-active`;

  useEffect(() => {
    setValue(defaultValue);
  }, [defaultValue]);

  // შემოთავაზებების ჩატვირთვა
  useEffect(() => {
    if (debounced.length < MIN_QUERY) {
      setResults([]);
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    api
      .searchProducts(debounced, SUGGESTION_LIMIT)
      .then((items) => !cancelled && setResults(items))
      .catch(() => !cancelled && setResults([]))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  // გარეთ დაკლიკებაზე დახურვა
  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const trimmed = value.trim();
  const mode = trimmed.length >= MIN_QUERY ? 'results' : 'recent';
  const showDropdown = open && (mode === 'results' || recent.length > 0);

  /** რამდენი ელემენტია კლავიატურით გასავლელი */
  const optionsCount = useMemo(() => {
    if (!showDropdown) return 0;
    if (mode === 'recent') return recent.length;
    return results.length > 0 ? results.length + 1 : 0;
  }, [showDropdown, mode, recent.length, results.length]);

  const closeDropdown = useCallback(() => {
    setOpen(false);
    setActiveIndex(-1);
    inputRef.current?.blur();
  }, []);

  const goToResults = useCallback(
    (term) => {
      const query = String(term ?? value).trim();
      if (!query) return;
      remember(query);
      closeDropdown();
      navigate(`/search?${QUERY_KEYS.search}=${encodeURIComponent(query)}`);
      onSubmitted?.(query);
    },
    [closeDropdown, navigate, onSubmitted, remember, value],
  );

  const goToProduct = useCallback(
    (product) => {
      remember(trimmed);
      closeDropdown();
      navigate(`/product/${product.slug}`);
      onSubmitted?.(product.name);
    },
    [closeDropdown, navigate, onSubmitted, remember, trimmed],
  );

  const selectRecent = useCallback(
    (term) => {
      setValue(term);
      goToResults(term);
    },
    [goToResults],
  );

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      setOpen(false);
      setActiveIndex(-1);
      return;
    }
    if (event.key === 'ArrowDown' && optionsCount > 0) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((i) => (i + 1) % optionsCount);
      return;
    }
    if (event.key === 'ArrowUp' && optionsCount > 0) {
      event.preventDefault();
      setActiveIndex((i) => (i - 1 + optionsCount) % optionsCount);
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      if (mode === 'recent' && activeIndex >= 0) selectRecent(recent[activeIndex]);
      else if (mode === 'results' && activeIndex >= 0 && activeIndex < results.length) {
        goToProduct(results[activeIndex]);
      } else goToResults();
    }
  }

  return (
    <div ref={wrapperRef} className={`relative ${className}`}>
      <form
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          goToResults();
        }}
      >
        <label htmlFor={`${listId}-input`} className="sr-only">
          {TEXT.search}
        </label>
        <Search
          className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500"
          aria-hidden="true"
        />
        <input
          ref={inputRef}
          id={`${listId}-input`}
          type="search"
          value={value}
          autoFocus={autoFocus}
          placeholder={TEXT.searchPlaceholder}
          role="combobox"
          aria-expanded={showDropdown}
          aria-controls={listId}
          aria-activedescendant={activeIndex >= 0 ? optionId : undefined}
          aria-autocomplete="list"
          autoComplete="off"
          onChange={(event) => {
            setValue(event.target.value);
            setOpen(true);
            setActiveIndex(-1);
          }}
          onFocus={() => {
            sync();
            setOpen(true);
          }}
          onKeyDown={handleKeyDown}
          className="h-11 w-full rounded-control border border-ink-200 bg-ink-50 pl-10 pr-10 text-sm text-ink-900 transition-colors placeholder:text-ink-500 hover:bg-white focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/25 [&::-webkit-search-cancel-button]:hidden"
        />

        {value && (
          <button
            type="button"
            onClick={() => {
              setValue('');
              setResults([]);
              setActiveIndex(-1);
              inputRef.current?.focus();
            }}
            aria-label="ძებნის გასუფთავება"
            className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-700"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </form>

      {showDropdown && (
        <SearchSuggestions
          mode={mode}
          results={results}
          recent={recent}
          loading={loading}
          query={trimmed}
          activeIndex={activeIndex}
          onSelect={goToProduct}
          onSelectRecent={selectRecent}
          onForgetRecent={forget}
          onClearRecent={clear}
          onViewAll={() => goToResults()}
          listId={listId}
          optionId={optionId}
        />
      )}
    </div>
  );
}
