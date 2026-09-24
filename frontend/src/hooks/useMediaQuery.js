import { useCallback, useSyncExternalStore } from 'react';

/**
 * CSS media query-ის მიმდინარე შედეგი, ცვლილებაზე განახლებით.
 * `matchMedia` თუ არ არსებობს (jsdom, ძველი გარემო) — false.
 */
export function useMediaQuery(query) {
  const subscribe = useCallback(
    (onChange) => {
      if (typeof window.matchMedia !== 'function') return () => {};
      const list = window.matchMedia(query);
      list.addEventListener('change', onChange);
      return () => list.removeEventListener('change', onChange);
    },
    [query]
  );
  return useSyncExternalStore(
    subscribe,
    () => typeof window.matchMedia === 'function' && window.matchMedia(query).matches,
    () => false
  );
}
