/**
 * A storefront `primary` fill never carries white text.
 *
 * In the dark theme `primary-600` (and its hover / press steps) is gold, and
 * white on gold is 2.24:1 (AA needs 4.5). `text-on-primary` is the role that
 * stays readable on it in both themes. The skip link slipped through with
 * `focus:bg-primary-600 ... focus:text-white`.
 *
 * Matching: a "unit" is one quoted string in a .js/.jsx file (a className) or
 * one `@apply ...;` statement in a .css file. A unit fails when it holds both
 * a `bg-primary-(600|hover|press)` token and a `text-white` token, each with
 * any variant prefix (`focus:`, `hover:`, `md:` ...). Prefixes are not
 * compared: the same string pairing the two is the smell. Skipped: the admin
 * panel (its `primary` stays as it was) and tests.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import { describe, expect, it } from 'vitest';

// `process.cwd()` rather than import.meta.url: under jsdom that is not a
// file: URL. Vitest runs from the frontend root.
const ROOT = process.cwd();
const SRC = join(ROOT, 'src');

const PRIMARY_FILL = /(?:^|\s)(?:[\w[\]-]+:)*bg-primary-(?:600|hover|press)(?:\/\d+)?(?=\s|$)/;
const WHITE_TEXT = /(?:^|\s)(?:[\w[\]-]+:)*text-white(?=\s|$)/;

const STRING = /(["'`])((?:\\.|(?!\1)[^\\])*)\1/gs;
const APPLY = /@apply\s+([^;]*);/g;

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return entry === 'admin' ? [] : sourceFiles(full);
    return /\.(jsx?|css)$/.test(entry) && !entry.includes('.test.') ? [full] : [];
  });
}

function units(file, text) {
  const pattern = file.endsWith('.css') ? APPLY : STRING;
  const group = file.endsWith('.css') ? 1 : 2;
  return [...text.matchAll(pattern)].map((m) => ({
    value: m[group],
    line: text.slice(0, m.index).split('\n').length,
  }));
}

function offenders(file, text) {
  return units(file, text)
    .filter(({ value }) => PRIMARY_FILL.test(value) && WHITE_TEXT.test(value))
    .map(({ value, line }) => `${relative(ROOT, file)}:${line}: ${value.replace(/\s+/g, ' ').trim()}`);
}

const files = sourceFiles(SRC);

describe('primary fills and white text', () => {
  it('finds the files to check', () => {
    expect(files.length).toBeGreaterThan(50);
    expect(files.some((f) => f.endsWith('index.css'))).toBe(true);
    expect(files.some((f) => f.endsWith('Layout.jsx'))).toBe(true);
  });

  it('catches the pairing in a class string and in @apply, with variants', () => {
    expect(offenders('a.jsx', '<a className="focus:bg-primary-600 px-4 focus:text-white" />')).toHaveLength(1);
    expect(offenders('a.css', '.x {\n @apply bg-primary-hover\n text-white;\n}')).toHaveLength(1);
    expect(offenders('a.jsx', "<a className='bg-primary-600 text-on-primary' />")).toHaveLength(0);
    expect(offenders('a.jsx', '<a className="bg-primary-50 text-white" />')).toHaveLength(0);
  });

  it('puts no white text on a primary fill', () => {
    const found = files.flatMap((file) => offenders(file, readFileSync(file, 'utf8')));
    expect(found).toEqual([]);
  });
});
