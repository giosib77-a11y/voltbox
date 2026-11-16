/**
 * The two translation files, and the source that reads them.
 *
 * What it covers: that Georgian and English have the same keys, both ways; that
 * every key the source asks for by name is there; and that no Georgian
 * interface text is left written into a storefront file - in the style of
 * storefrontCopy.test.js, by reading the source.
 *
 * Why the last one matters most: a sentence left in a component is not a
 * failure anyone sees in Georgian. It is the one Georgian line on an English
 * page, found by a shopper.
 *
 * What is skipped, and why - each is Georgian on purpose:
 *   admin/                 the admin panel is Georgian only
 *   data/, mockApi.js      the development catalogue and the fake backend that
 *                          serves it: records and server messages, not copy
 *   utils/search.js        Georgian suffixes and unit names the search matches
 *                          a query against - logic, not text to show
 *   colorSwatches.js       colour values as the catalogue spells them (API data)
 *   new Error('...')       a message for a developer, not a shopper
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

import { describe, expect, it } from 'vitest';

import ka from './ka.json';
import en from './en.json';
// The admin's error texts, registered on top of ka by the admin chunk. The
// storefront source asks for some of them by name (httpClient's image errors).
import adminKa from '../admin/i18n/ka.json';

const ROOT = process.cwd();
const SRC = join(ROOT, 'src');

const SKIP_DIRS = ['admin', 'data'];
const SKIP_FILES = [
  ['services', 'mockApi.js'],
  ['utils', 'search.js'],
  ['constants', 'colorSwatches.js'],
].map((parts) => join(SRC, ...parts));

const GEORGIAN = /[ა-ჿ]/;

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return SKIP_DIRS.includes(entry) ? [] : sourceFiles(full);
    return /\.jsx?$/.test(entry) && !entry.includes('.test.') ? [full] : [];
  });
}

/** Every leaf as a dotted path; an array is one leaf of its length. */
function leaves(node, prefix = '') {
  return Object.entries(node).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (Array.isArray(value)) return [`${path}[${value.length}]`];
    return value && typeof value === 'object' ? leaves(value, path) : [path];
  });
}

/**
 * The code without its comments, line for line (a removed comment leaves its
 * newlines, so a finding still names the right line). Block comments, JSX
 * comments, and `//` comments that start a line or follow a space.
 */
function withoutComments(text) {
  const blank = (match) => match.replace(/[^\n]/g, ' ');
  return text
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, blank)
    .replace(/\/\*[\s\S]*?\*\//g, blank)
    .replace(/(^|\s)\/\/.*$/gm, (match, before) => before + ' '.repeat(match.length - before.length));
}

function hardcodedGeorgian(file) {
  return withoutComments(readFileSync(file, 'utf8'))
    .split('\n')
    .map((line, i) => [line, i])
    .filter(([line]) => GEORGIAN.test(line) && !/\bnew Error\(/.test(line))
    .map(([line, i]) => `${relative(ROOT, file)}:${i + 1}: ${line.trim()}`);
}

const files = sourceFiles(SRC).filter((file) => !SKIP_FILES.includes(file));

describe('the translation files', () => {
  it('have every Georgian key in English', () => {
    const english = new Set(leaves(en));
    expect(leaves(ka).filter((key) => !english.has(key))).toEqual([]);
  });

  it('have every English key in Georgian', () => {
    const georgian = new Set(leaves(ka));
    expect(leaves(en).filter((key) => !georgian.has(key))).toEqual([]);
  });

  it('leave no value empty', () => {
    const empty = (tree) => leaves(tree).filter((path) => {
      const value = path.replace(/\[\d+\]$/, '').split('.').reduce((node, key) => node?.[key], tree);
      return value === '' || (Array.isArray(value) && value.some((item) => !item));
    });
    expect([...empty(ka), ...empty(en), ...empty(adminKa)]).toEqual([]);
  });

  it('keep the admin error texts out of the storefront files, and no code in both', () => {
    // Admin-only texts in ka.json or en.json would ship in the storefront's
    // entry chunk (or the English one) again.
    const shared = Object.keys(ka.apiErrors);
    expect(Object.keys(adminKa.apiErrors).filter((code) => shared.includes(code))).toEqual([]);
    expect(Object.keys(adminKa)).toEqual(['apiErrors']);
  });
});

describe('the keys the source asks for', () => {
  // Literal keys only: `t('cart.title')`, `<Rich k="..." />` and
  // the `labelKey` / `titleKey` / `title: 'home...'` entries of the lists that
  // hold keys. A key built at runtime - `sort.${value}` - is not read here.
  const KEY_PATTERNS = [
    /\bt\(\s*'([\w.]+)'/g,
    /<Rich\s+k="([\w.]+)"/g,
    /\b(?:labelKey|titleKey|title|text):\s*'([a-z][\w]*\.[\w.]+)'/g,
  ];

  // The admin's keys count only for the one shared file that looks them up
  // (httpClient's image errors): in any other storefront file they would show
  // as a raw key, because the shop never loads the admin chunk.
  const mayUseAdminKeys = (file) => file.endsWith(join('services', 'httpClient.js'));

  const exists = (key, file) => {
    const node = (suffix, tree) => `${key}${suffix}`.split('.').reduce((at, part) => at?.[part], tree);
    const trees = mayUseAdminKeys(file) ? [ka, adminKa] : [ka];
    return trees.some((tree) => node('', tree) !== undefined || node('_one', tree) !== undefined);
  };

  it('finds keys to check', () => {
    // Guards the test: a pattern that stopped matching would pass silently.
    const all = files.flatMap((file) =>
      KEY_PATTERNS.flatMap((pattern) => [...readFileSync(file, 'utf8').matchAll(pattern)]),
    );
    expect(all.length).toBeGreaterThan(300);
  });

  it('are all in the translation files', () => {
    const missing = files.flatMap((file) => {
      const text = withoutComments(readFileSync(file, 'utf8'));
      return KEY_PATTERNS.flatMap((pattern) => [...text.matchAll(pattern)])
        .map((match) => match[1])
        .filter((key) => !exists(key, file))
        .map((key) => `${relative(ROOT, file)}: ${key}`);
    });
    expect(missing).toEqual([]);
  });
});

describe('the storefront source', () => {
  it('finds the files to check', () => {
    expect(files.length).toBeGreaterThan(80);
    for (const name of ['Header.jsx', 'Checkout.jsx', 'httpClient.js', 'validate.js', 'InfoPage.jsx']) {
      expect(files.some((file) => file.endsWith(`${sep}${name}`))).toBe(true);
    }
    expect(files.some((file) => file.includes(`${sep}admin${sep}`))).toBe(false);
  });

  it('writes no Georgian interface text of its own', () => {
    expect(files.flatMap(hardcodedGeorgian)).toEqual([]);
  });
});
