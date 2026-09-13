/**
 * Every field a shopper types into is at least 16px on a phone.
 *
 * iOS Safari zooms the page when a focused input's font-size is below 16px.
 * Every control on the site was `text-sm` (14px), so tapping the search box or
 * any checkout field jumped the layout and left the shopper pinching back out
 * - on a shop whose traffic is mostly phones.
 *
 * The alternative fix is `maximum-scale=1` in the viewport tag, which disables
 * zoom for everybody, including the people who need it. That is not on the
 * table, so the rule is a shared `.field-text` class instead.
 *
 * This reads the source rather than rendering, because jsdom computes no
 * layout and Tailwind classes are just strings to it either way. Reading the
 * files also catches a field added later, which is the actual risk.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// `process.cwd()` rather than import.meta.url: under jsdom that is not a
// file: URL and fileURLToPath refuses it. Vitest runs from the frontend root.
const SRC = join(process.cwd(), 'src');

/** The admin panel is used at a desk; this rule is about the shop. */
const SKIP = ['admin', '__tests__'];

const TYPED_INTO = /<(input|textarea|select)\b/g;

//: `type` values that never take a keyboard, so no zoom and no rule.
const NOT_TYPED_INTO = ['checkbox', 'radio', 'range', 'file', 'hidden', 'submit', 'button'];

function jsxFiles(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return SKIP.includes(entry) ? [] : jsxFiles(full);
    return entry.endsWith('.jsx') && !entry.includes('.test.') ? [full] : [];
  });
}

/** The whole opening tag of each field, however many lines it spans. */
function fieldTags(source) {
  const tags = [];
  for (const match of source.matchAll(TYPED_INTO)) {
    const start = match.index;
    let depth = 0;
    for (let i = start; i < source.length; i += 1) {
      const char = source[i];
      if (char === '{') depth += 1;
      else if (char === '}') depth -= 1;
      else if (char === '>' && depth === 0) {
        tags.push(source.slice(start, i + 1));
        break;
      }
    }
  }
  return tags;
}

const files = jsxFiles(SRC);

describe('the size of a field on a phone', () => {
  it('finds the components to check', () => {
    // Guards the test: a moved directory would otherwise make it pass silently.
    expect(files.length).toBeGreaterThan(20);
    expect(files.some((f) => f.endsWith('Input.jsx'))).toBe(true);
  });

  it.each(files)('%s', (file) => {
    const source = readFileSync(file, 'utf8');

    for (const tag of fieldTags(source)) {
      const type = tag.match(/type="([a-z]+)"/)?.[1];
      if (type && NOT_TYPED_INTO.includes(type)) continue;
      // A field that takes its classes from a prop is sized by its caller.
      if (!/className=/.test(tag)) continue;

      expect(
        /field-text|text-base|dims\.input/.test(tag),
        `${file}\n\n${tag}\n\nA field a shopper types into needs .field-text, ` +
          'or iOS Safari zooms the page when it is focused.',
      ).toBe(true);
    }
  });
});
