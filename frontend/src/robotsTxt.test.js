/**
 * robots.txt keeps the private pages out of the index in both languages.
 *
 * The English storefront is mounted under the basename `/en`, so `/checkout`
 * does not cover `/en/checkout`: each private page needs a line per language.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// `process.cwd()` rather than import.meta.url: under jsdom that is not a
// file: URL. Vitest runs from the frontend root.
const lines = readFileSync(join(process.cwd(), 'public', 'robots.txt'), 'utf8')
  .split(/\r?\n/)
  .map((line) => line.trim());

describe('robots.txt', () => {
  it.each(['/checkout', '/account', '/cart'])('disallows %s in both languages', (path) => {
    expect(lines).toContain(`Disallow: ${path}`);
    expect(lines).toContain(`Disallow: /en${path}`);
  });

  it('still allows the rest of the site', () => {
    expect(lines).toContain('Allow: /');
  });
});
