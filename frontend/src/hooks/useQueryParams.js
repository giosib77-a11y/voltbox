import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DEFAULT_SORT, PAGE_SIZE, QUERY_KEYS } from '../constants/index.js';
import { parseFiltersFromParams, serializeFilters } from '../utils/filter.js';

/**
 * კატალოგის მდგომარეობა URL-ში.
 *
 * ფილტრები, სორტი, გვერდი და ძებნის ტექსტი ცხოვრობს query params-ში —
 * refresh-ის ან ბმულის გაზიარების შემდეგ ყველაფერი იდენტურად აღდგება.
 *
 * @param {import('../types.js').CategoryFilter[]} categoryFilters
 */
export function useCatalogParams(categoryFilters = [], options = {}) {
  const defaultSort = options.defaultSort ?? DEFAULT_SORT;
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(
    () => parseFiltersFromParams(searchParams, categoryFilters),
    [searchParams, categoryFilters],
  );

  const sort = searchParams.get(QUERY_KEYS.sort) || defaultSort;
  const page = Math.max(1, Number(searchParams.get(QUERY_KEYS.page)) || 1);
  const query = searchParams.get(QUERY_KEYS.search) || '';

  /** ახალი query-ს აწყობა და ნავიგაცია (ისტორიაში ჩანაცვლებით). */
  const commit = useCallback(
    (next, options = {}) => {
      const params = new URLSearchParams();

      // ძებნის ტექსტი ყოველთვის ინახება
      const nextQuery = next.query !== undefined ? next.query : query;
      if (nextQuery) params.set(QUERY_KEYS.search, nextQuery);

      const nextFilters = next.filters !== undefined ? next.filters : filters;
      Object.entries(serializeFilters(nextFilters, categoryFilters)).forEach(([key, value]) => {
        params.set(key, value);
      });

      const nextSort = next.sort !== undefined ? next.sort : sort;
      if (nextSort && nextSort !== defaultSort) params.set(QUERY_KEYS.sort, nextSort);

      const nextPage = next.page !== undefined ? next.page : 1;
      if (nextPage > 1) params.set(QUERY_KEYS.page, String(nextPage));

      setSearchParams(params, { replace: options.replace ?? false });
    },
    [categoryFilters, defaultSort, filters, query, setSearchParams, sort],
  );

  const setFilters = useCallback((nextFilters) => commit({ filters: nextFilters, page: 1 }), [commit]);
  const setSort = useCallback((nextSort) => commit({ sort: nextSort, page: 1 }), [commit]);
  const setPage = useCallback((nextPage) => commit({ page: nextPage }), [commit]);
  const setQuery = useCallback((nextQuery) => commit({ query: nextQuery, page: 1 }), [commit]);
  const clearFilters = useCallback(() => commit({ filters: {}, page: 1 }), [commit]);

  return {
    filters,
    sort,
    page,
    query,
    limit: PAGE_SIZE,
    setFilters,
    setSort,
    setPage,
    setQuery,
    clearFilters,
  };
}

export default useCatalogParams;
