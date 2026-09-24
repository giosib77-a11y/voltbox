/**
 * The storefront's light/dark theme: which one applies, and the shopper's choice.
 *
 * Until the shopper picks, the theme follows the system setting and keeps
 * following it if it changes. A pick is stored under STORAGE_KEYS.theme and
 * wins from then on. When storage refuses the write (private mode, a full
 * quota) the pick still holds for as long as the page is open.
 *
 * public/theme-init.js makes the same decision before the first paint, from
 * the same key; this module keeps the class on <html> in step afterwards.
 * The palettes behind the classes are in tailwind.config.js.
 */

import { STORAGE_KEYS } from '../constants/index.js';
import { readJSON, writeJSON } from './storage.js';

export const THEMES = ['light', 'dark'];
export const SYSTEM_DARK = '(prefers-color-scheme: dark)';

// A pick that storage refused to save, kept for as long as the page is open.
// Null whenever storage took the pick: then storage is the only copy.
let sessionChoice = null;
const listeners = new Set();

/** The shopper's pick, or null while the system setting decides. */
export function getChoice() {
  if (sessionChoice) return sessionChoice;
  const stored = readJSON(STORAGE_KEYS.theme, null);
  return THEMES.includes(stored) ? stored : null;
}

function systemTheme() {
  return typeof window.matchMedia === 'function' && window.matchMedia(SYSTEM_DARK).matches
    ? 'dark'
    : 'light';
}

/** The theme in effect: the pick if there is one, else the system's. */
export function getTheme() {
  return getChoice() ?? systemTheme();
}

export function setTheme(theme) {
  if (!THEMES.includes(theme)) return;
  sessionChoice = writeJSON(STORAGE_KEYS.theme, theme) ? null : theme;
  listeners.forEach((listener) => listener());
}

/** For useSyncExternalStore: a pick, or a change in the system setting. */
export function subscribe(onChange) {
  listeners.add(onChange);
  const list = typeof window.matchMedia === 'function' ? window.matchMedia(SYSTEM_DARK) : null;
  list?.addEventListener('change', onChange);
  return () => {
    listeners.delete(onChange);
    list?.removeEventListener('change', onChange);
  };
}

/** Puts `theme-light` or `theme-dark` on <html>, and only one of them. */
export function applyTheme(theme, root = document.documentElement) {
  THEMES.forEach((name) => root.classList.toggle(`theme-${name}`, name === theme));
}
