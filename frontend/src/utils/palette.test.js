/**
 * The storefront palettes, held to WCAG AA.
 *
 * Every text/background pair the shop actually draws, measured in both
 * themes straight from tailwind.config.js: 4.5:1 for text, 3:1 for large text
 * and for the borders and icons a shopper needs to see a control. Dark themes
 * usually fail on muted grey; lighter dark themes fail on borders, which fade
 * as the background rises to meet them. Change a value and this re-measures.
 *
 * The admin palette is not checked for contrast: it is frozen as it was, and
 * some of its pairs are below AA. It is pinned instead (further down) to the
 * literals it had before the storefront redesign.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { expect, it } from 'vitest';

import config, { palette, themeTokens } from '../../tailwind.config.js';

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
// = DESIGN.md §2.4. `outline` is not here on purpose: it contours buttons that
// carry their own label or icon, so WCAG 1.4.11 does not ask 3:1 of it.
const PAIRS = [
  ['body text', 4.5, ['ink-900', 'ink-800', 'ink-700', 'ink-600'], ['canvas', 'surface', 'ink-100']],
  ['text on a hovered menu row', 4.5, ['ink-700'], ['ink-200']],
  ['muted text, placeholders, old price', 4.5, ['ink-500'], ['canvas', 'surface', 'ink-100', 'primary-50', 'footer']],
  ['links, eyebrow, brand label, active nav', 4.5, ['primary-700'], ['canvas', 'surface', 'ink-100', 'primary-50', 'primary-100', 'footer']],
  ['text on a tint', 4.5, ['primary-800'], ['primary-50']],
  ['text on a primary fill', 4.5, ['on-primary'], ['primary-600', 'primary-hover', 'primary-press']],
  ['white on solid fills', 4.5, ['white'], ['accent-600', 'accent-700', 'danger-600', 'danger-700']],
  ['secondary button, stock badge', 4.5, ['surface'], ['ink-900', 'ink-800', 'ink-950']],
  ['out-of-stock pill', 4.5, ['white'], ['scrim']],
  ['error text', 4.5, ['danger-fg'], ['canvas', 'surface', 'danger-50']],
  ['savings, discount text', 4.5, ['accent-fg'], ['canvas', 'surface', 'accent-50']],
  ['success text', 4.5, ['success-700'], ['surface', 'success-50']],
  ['warning text', 4.5, ['warning-600'], ['surface', 'warning-50']],
  ['selected text', 4.5, ['ink-900'], ['primary-200']],
  ['footer text', 4.5, ['ink-600'], ['footer']],
  ['control borders', 3, ['ink-300'], ['canvas', 'surface', 'ink-100', 'primary-50']],
  ['icons, separators', 3, ['ink-400'], ['canvas', 'surface', 'ink-100', 'primary-50']],
  ['error border', 3, ['danger-500'], ['canvas', 'surface', 'ink-100']],
  ['gold ornament, focus ring, round-button outline', 3, ['primary-500'], ['canvas', 'surface', 'ink-100', 'primary-50', 'footer']],
  ['checked box, active page, slider fill', 3, ['primary-600'], ['canvas', 'surface']],
  ['rating stars', 3, ['accent-400'], ['canvas', 'surface']],
  ['success icon', 3, ['success-600'], ['canvas', 'surface']],
  ['placeholder drawing on the photo tile', 3, ['ink-400'], ['media']],
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
  // the roles the redesign added: a theme that lacks one would render it unset
  for (const theme of Object.values(palette)) {
    for (const role of ['on-primary', 'footer', 'glow', 'outline']) {
      expect(theme[role]).toMatch(/^#[0-9a-f]{6}$/i);
    }
  }
});

it('defines the same radius, shadow, stroke and button tokens in every theme', () => {
  const names = (tokens) => Object.keys(tokens).sort();
  expect(names(themeTokens.light)).toEqual(names(themeTokens.admin));
  expect(names(themeTokens.dark)).toEqual(names(themeTokens.admin));
});

// The admin panel is frozen (Decision Log 2026-10-19). Every value below is a
// literal copied from tailwind.config.js as it was before the redesign, not
// read back from it: an edit to the admin palette or to a token the panel
// shares (Button, Input, Modal, Toast, ...) must fail here, in one place.
const ADMIN_COLOURS = {
  surface: '#ffffff',
  media: '#eef0f4',
  'media-shade': '#dde1e9',
  scrim: '#12151d',
  ink: {
    50: '#f7f8fa',
    100: '#eef0f4',
    200: '#dde1e9',
    300: '#c2c9d6',
    400: '#97a1b5',
    500: '#657086',
    600: '#56617a',
    700: '#454e63',
    800: '#333a4a',
    900: '#1e2330',
    950: '#12151d',
  },
  primary: {
    50: '#eef3ff',
    100: '#dbe5ff',
    200: '#bfd0ff',
    300: '#94b0ff',
    400: '#6285ff',
    500: '#3a5bf5',
    600: '#2440e0',
    700: '#1e33bd',
    800: '#1d2f99',
    900: '#1e2e79',
    950: '#141c47',
    hover: '#1e33bd',
    press: '#1d2f99',
  },
  accent: {
    50: '#fff8ed',
    100: '#ffefd4',
    200: '#ffdba8',
    300: '#ffc071',
    400: '#ff9c38',
    500: '#ff7f11',
    600: '#c74407',
    700: '#9e360e',
    800: '#7f2e0f',
    900: '#66250c',
    fg: '#c74407',
  },
  success: { 50: '#ecfdf5', 100: '#d1fae5', 500: '#10b981', 600: '#059669', 700: '#047857' },
  danger: { 50: '#fef2f2', 100: '#fee2e2', 500: '#ef4444', 600: '#dc2626', 700: '#b91c1c', fg: '#dc2626' },
  warning: { 50: '#fffbeb', 100: '#fef3c7', 500: '#f59e0b', 600: '#aa5d05' },
  // new roles: what the panel drew before they existed
  'on-primary': '#ffffff',
  footer: '#ffffff',
  glow: '#eef3ff',
  outline: '#c2c9d6',
};

const ADMIN_TOKENS = {
  'radius-control': '0.625rem',
  'radius-card': '0.875rem',
  'shadow-card': '0 1px 2px 0 rgb(18 21 29 / 0.04), 0 1px 3px 0 rgb(18 21 29 / 0.06)',
  'shadow-card-hover': '0 10px 24px -6px rgb(18 21 29 / 0.14), 0 2px 6px -2px rgb(18 21 29 / 0.08)',
  'shadow-popover': '0 12px 32px -8px rgb(18 21 29 / 0.22), 0 4px 10px -4px rgb(18 21 29 / 0.10)',
  'shadow-header': '0 1px 0 0 rgb(18 21 29 / 0.06)',
  'shadow-glow': '0 0 0 1px rgb(var(--c-primary-400) / 0.25), 0 14px 36px -14px rgb(var(--c-primary-600) / 0.6)',
  'shadow-btn': '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  'focus-radius': '0.125rem',
  'icon-stroke': '2',
  'icon-stroke-fine': '2',
  'btn-weight': '600',
  'btn-tracking': '0',
};

it('keeps every admin colour exactly as the panel had it', () => {
  expect(palette.admin).toEqual(ADMIN_COLOURS);
});

it('keeps every admin radius, shadow, stroke and button token exactly as the panel had it', () => {
  expect(themeTokens.admin).toEqual(ADMIN_TOKENS);
});

it('points radius and shadow classes at the theme variables, not at literals', () => {
  const { borderRadius, boxShadow } = config.theme.extend;
  expect(borderRadius.card).toBe('var(--radius-card)');
  expect(borderRadius.control).toBe('var(--radius-control)');
  for (const name of ['card', 'card-hover', 'popover', 'header', 'glow', 'btn']) {
    expect(boxShadow[name]).toBe(`var(--shadow-${name})`);
  }
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
