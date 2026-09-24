/**
 * The storefront palettes, held to WCAG AA.
 *
 * Every text/background pair the shop actually draws, measured in both
 * themes straight from tailwind.config.js: 4.5:1 for text, 3:1 for large text
 * and for the borders and icons a shopper needs to see a control. Dark themes
 * usually fail on muted grey; lighter dark themes fail on borders, which fade
 * as the background rises to meet them. Change a value and this re-measures.
 *
 * The admin palette is not checked: it is frozen as it was, and some of its
 * pairs are below AA. The storefront `light` theme is that palette with those
 * pairs corrected.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { expect, it } from 'vitest';

import { palette } from '../../tailwind.config.js';

/** WCAG 2 relative luminance → contrast ratio. */
function contrast(a, b) {
  const luminance = (hex) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** `ink-500` → the theme's hex. `canvas` is ink-50, as in the config. */
function colour(theme, token) {
  if (token === 'white') return '#ffffff';
  if (token === 'canvas') return theme.ink[50];
  if (typeof theme[token] === 'string') return theme[token];
  const cut = token.lastIndexOf('-');
  return theme[token.slice(0, cut)][token.slice(cut + 1)];
}

// [what it is, minimum, foregrounds, backgrounds they sit on]
const PAIRS = [
  ['body text', 4.5, ['ink-900', 'ink-800', 'ink-700', 'ink-600'], ['canvas', 'surface', 'ink-100']],
  ['text on a hovered menu row', 4.5, ['ink-700'], ['ink-200']],
  ['muted text, placeholders', 4.5, ['ink-500'], ['canvas', 'surface', 'ink-100', 'primary-50']],
  ['links, active nav', 4.5, ['primary-700'], ['canvas', 'surface', 'ink-100', 'primary-50']],
  ['hero pill, active nav', 4.5, ['primary-800'], ['primary-50']],
  ['white on solid fills', 4.5, ['white'], ['primary-600', 'primary-hover', 'primary-press', 'accent-600', 'danger-600']],
  ['secondary button, stock badge', 4.5, ['surface'], ['ink-900']],
  ['out-of-stock pill', 4.5, ['white'], ['scrim']],
  ['error text', 4.5, ['danger-fg'], ['canvas', 'surface', 'danger-50']],
  ['savings, admin link', 4.5, ['accent-fg'], ['canvas', 'surface', 'accent-50']],
  ['success text', 4.5, ['success-700'], ['surface', 'success-50']],
  ['warning text', 4.5, ['warning-600'], ['surface', 'warning-50']],
  ['hero heading gradient (large)', 3, ['primary-700', 'primary-500'], ['surface']],
  ['control borders', 3, ['ink-300'], ['canvas', 'surface', 'ink-100']],
  ['icons, separators', 3, ['ink-400'], ['canvas', 'surface', 'ink-100']],
  ['checked box, active page, slider', 3, ['primary-600'], ['canvas', 'surface']],
  ['focus ring', 3, ['primary-500'], ['canvas', 'surface', 'ink-100']],
  ['rating stars', 3, ['accent-400'], ['surface']],
];

it.each(['light', 'dark'])('the %s storefront theme meets WCAG AA on every pair', (name) => {
  const theme = palette[name];
  const failures = PAIRS.flatMap(([role, min, fgs, bgs]) =>
    fgs.flatMap((fg) =>
      bgs
        .map((bg) => [bg, contrast(colour(theme, fg), colour(theme, bg))])
        .filter(([, ratio]) => ratio < min)
        .map(([bg, ratio]) => `${role}: ${fg} on ${bg} is ${ratio.toFixed(2)}, needs ${min}`),
    ),
  );
  expect(failures).toEqual([]);
});

it('defines the same tokens in every theme', () => {
  const shape = (theme) =>
    Object.entries(theme)
      .map(([key, value]) => (typeof value === 'string' ? key : `${key}:${Object.keys(value).join(',')}`))
      .sort();
  expect(shape(palette.light)).toEqual(shape(palette.admin));
  expect(shape(palette.dark)).toEqual(shape(palette.admin));
});

it('has no colour written for one theme only', () => {
  // A `dark:` class paints one element in one theme, outside the palette.
  // Tailwind's default darkMode would also key it to the OS, not the switch.
  const files = (dir) =>
    readdirSync(dir).flatMap((entry) => {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) return files(full);
      return /\.(jsx?|css)$/.test(entry) && !entry.includes('.test.') ? [full] : [];
    });
  const offenders = files(join(process.cwd(), 'src')).filter((file) =>
    /(^|[\s"'`])dark:/.test(readFileSync(file, 'utf8')),
  );
  expect(offenders).toEqual([]);
});
