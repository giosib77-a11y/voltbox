/**
 * Shared by the theme tests: a controllable system colour scheme, and the
 * real public/theme-init.js run the way a page load runs it.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

// `process.cwd()`: vitest runs from the frontend root (see fieldSize.test.js).
const INIT_SOURCE = readFileSync(join(process.cwd(), 'public', 'theme-init.js'), 'utf8');

/** Installs window.matchMedia answering prefers-color-scheme; returns a setter. */
export function mockSystemScheme(dark) {
  const state = { dark };
  const listeners = new Set();
  const list = {
    get matches() {
      return state.dark;
    },
    addEventListener: (_type, listener) => listeners.add(listener),
    removeEventListener: (_type, listener) => listeners.delete(listener),
  };
  window.matchMedia = () => list;
  return {
    set(nextDark) {
      state.dark = nextDark;
      listeners.forEach((listener) => listener());
    },
  };
}

export function removeSystemScheme() {
  delete window.matchMedia;
}

/** A page load: clears <html>'s classes and runs the head script. */
export function runThemeInit() {
  document.documentElement.className = '';
  new Function(INIT_SOURCE)();
  return document.documentElement.className;
}
