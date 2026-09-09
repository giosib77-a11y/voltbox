import { useCallback } from 'react';
import { useLocalStorage } from './useLocalStorage.js';
import { readJSON } from '../utils/storage.js';
import { STORAGE_KEYS } from '../constants/index.js';

/** რამდენი ბოლო ძებნა ვინახოთ. */
export const RECENT_LIMIT = 5;

/**
 * ბოლო ძებნების ისტორია (`recent-searches:v1`).
 *
 * Header-ში SearchBar ორჯერ ირენდერება (desktop და mobile), ამიტომ ჩაწერამდე
 * ყოველთვის ვკითხულობთ localStorage-ს — თორემ უხილავი ეგზემპლარის მოძველებული
 * state გადააწერდა ხილულის ჩანაწერს.
 */
export function useRecentSearches() {
  const [recent, setRecent] = useLocalStorage(STORAGE_KEYS.recentSearches, []);

  const read = () => {
    const stored = readJSON(STORAGE_KEYS.recentSearches, []);
    return Array.isArray(stored) ? stored.filter((v) => typeof v === 'string') : [];
  };

  /** მეორე ეგზემპლარის ცვლილების აყოლა — ველზე ფოკუსისას. */
  const sync = useCallback(() => setRecent(read()), [setRecent]);

  const remember = useCallback(
    (term) => {
      const value = String(term || '').trim();
      if (value.length < 2) return;
      const withoutDuplicate = read().filter((v) => v.toLowerCase() !== value.toLowerCase());
      setRecent([value, ...withoutDuplicate].slice(0, RECENT_LIMIT));
    },
    [setRecent],
  );

  const forget = useCallback(
    (term) => setRecent(read().filter((v) => v !== term)),
    [setRecent],
  );

  const clear = useCallback(() => setRecent([]), [setRecent]);

  return {
    recent: Array.isArray(recent) ? recent : [],
    remember,
    forget,
    clear,
    sync,
  };
}

export default useRecentSearches;
