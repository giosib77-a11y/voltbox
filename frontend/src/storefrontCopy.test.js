/**
 * No storefront text offers phones as something the shop sells.
 *
 * The owner deleted the Phones category: the shop does not sell phones for
 * now. The hero, the footer and the meta description still listed "ტელეფონები"
 * first among the product lines, all from one sentence in constants, with two
 * copies in index.html for the crawlers that do not run JavaScript.
 *
 * The plural is what names a product line - "ტელეფონები", "ტელეფონების" - and
 * "სმარტფონი" names the product. The singular stays: "ტელეფონი", "ტელეფონით",
 * "ტელეფონის ნომერი" are the contact number in the forms and on the info pages.
 *
 * Notes: reads the source and the two translation files, where the copy
 * lives since the English version - so a sentence added later is caught too,
 * in either language ("phones", "smartphone" in English). Skipped:
 * the admin panel, which names whatever categories exist; `data/`, the
 * catalogue the mock API serves in development - a fake backend's records, not
 * the shop's copy; and tests. og-image.png carries the same list drawn as
 * pixels, which this cannot read - it was checked by eye.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import { describe, expect, it } from 'vitest';

import ka from './i18n/ka.json';

// `process.cwd()` rather than import.meta.url: under jsdom that is not a
// file: URL. Vitest runs from the frontend root.
const ROOT = process.cwd();
const SRC = join(ROOT, 'src');

const SKIP = ['admin', 'data'];

const PHONES_AS_PRODUCT_LINE = /ტელეფონებ|სმარტფონ/;
// English only where English copy is: in source, "Smartphone" is an icon's name.
const PHONES_IN_ENGLISH = /phones|smartphone/i;

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return SKIP.includes(entry) ? [] : sourceFiles(full);
    return /\.jsx?$/.test(entry) && !entry.includes('.test.') ? [full] : [];
  });
}

const files = [
  ...sourceFiles(SRC),
  join(ROOT, 'index.html'),
  join(SRC, 'i18n', 'ka.json'),
  join(SRC, 'i18n', 'en.json'),
];

describe('what the storefront says it sells', () => {
  it('finds the files to check', () => {
    // Guards the test: a moved directory would otherwise make it pass silently.
    expect(files.length).toBeGreaterThan(50);
    expect(files.some((f) => f.endsWith('Home.jsx'))).toBe(true);
    expect(files.some((f) => f.endsWith('Footer.jsx'))).toBe(true);
  });

  it('lists no phones among the product lines', () => {
    const found = files.flatMap((file) =>
      readFileSync(file, 'utf8')
        .split('\n')
        .map((line, i) => [line, i])
        .filter(
          ([line]) =>
            PHONES_AS_PRODUCT_LINE.test(line) || (file.endsWith('en.json') && PHONES_IN_ENGLISH.test(line)),
        )
        .map(([line, i]) => `${relative(ROOT, file)}:${i + 1}: ${line.trim()}`),
    );
    expect(found).toEqual([]);
  });

  it('names what the shop does sell', () => {
    for (const line of ['კაბელები', 'დამტენები', 'Power Bank', 'ყურსასმენები', 'აქსესუარები']) {
      expect(ka.site.description).toContain(line);
    }
  });
});
