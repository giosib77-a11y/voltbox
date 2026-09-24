import { useSyncExternalStore } from 'react';
import { getTheme, setTheme, subscribe } from '../utils/theme.js';

/**
 * The storefront theme in effect and a setter for the shopper's pick.
 * Every caller sees the same value; see utils/theme.js for the rules.
 */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getTheme, () => 'light');
  return [theme, setTheme];
}
