/**
 * Tests for the filter URL round trip.
 *
 * What they cover: that a filter survives being written into the address bar
 * and read back, and that the price range agrees with the server about which
 * strings are a range at all.
 *
 * The second half is the one that bit. `Number('')` is 0, so `price=-50` split
 * on its dash reads as 0–50 here while `Decimal('')` raises on the server and
 * the filter is dropped. The sidebar would then show a range the results do not
 * reflect - the filter looks applied and is not.
 */

import { describe, expect, it } from 'vitest';

import {
  buildFilterChips,
  countActiveFilters,
  parseFiltersFromParams,
  paramForFilter,
  serializeFilters,
  withFacetLabels,
} from './filter.js';

const CONFIG = [
  { key: 'brand', type: 'list' },
  { key: 'specs.ram', type: 'list' },
  { key: 'specs.wireless', type: 'toggle', match: true },
];

const parse = (query) => parseFiltersFromParams(new URLSearchParams(query), CONFIG);

describe('paramForFilter', () => {
  it('uses the last segment of a dotted key', () => {
    expect(paramForFilter({ key: 'specs.ram' })).toBe('ram');
  });

  it('prefers an explicit param name', () => {
    expect(paramForFilter({ key: 'specs.ram', param: 'memory' })).toBe('memory');
  });
});

describe('the URL round trip', () => {
  it.each([
    [{ brand: ['Samsung'] }],
    [{ brand: ['Samsung', 'Anker'] }],
    [{ 'specs.ram': ['8GB'] }],
    [{ 'specs.wireless': true }],
    [{ price: [100, 500] }],
    [{ brand: ['Samsung'], 'specs.ram': ['8GB'], price: [0, 50] }],
  ])('survives serialize then parse: %j', (filters) => {
    const entries = serializeFilters(filters, CONFIG);
    const back = parse(new URLSearchParams(entries).toString());

    expect(back).toEqual(filters);
  });

  it('drops a toggle that is off rather than writing false', () => {
    expect(serializeFilters({ 'specs.wireless': false }, CONFIG)).toEqual({});
  });

  it('drops an empty list rather than writing an empty param', () => {
    expect(serializeFilters({ brand: [] }, CONFIG)).toEqual({});
  });
});

describe('the price range, matched to what the server accepts', () => {
  it.each([
    ['price=100-500', [100, 500]],
    ['price=0-50', [0, 50]],
    ['price=12.5-99.9', [12.5, 99.9]],
    ['price=12-12', [12, 12]],
  ])('%s parses to %j', (query, expected) => {
    expect(parse(query).price).toEqual(expected);
  });

  it.each([
    ['price=-50', 'a missing lower bound, which Number() would read as 0'],
    ['price=10-', 'a missing upper bound'],
    ['price=abc', 'not a range at all'],
    ['price=500-100', 'inverted'],
    ['price=1-2-3', 'three parts'],
    ['price=', 'empty'],
    ['price=%20-50', 'whitespace where a number should be'],
  ])('%s is no filter at all (%s)', (query) => {
    expect(parse(query).price).toBeUndefined();
  });
});

describe('countActiveFilters', () => {
  it('counts each chosen value, a toggle once and a price range once', () => {
    const filters = {
      brand: ['Samsung', 'Anker'],
      'specs.wireless': true,
      price: [100, 500],
    };

    expect(countActiveFilters(filters)).toBe(4);
  });

  it('is zero for nothing chosen', () => {
    expect(countActiveFilters({})).toBe(0);
  });
});

describe('withFacetLabels', () => {
  const BRAND = { key: 'brand', label: 'Brand', type: 'checkbox' };
  const ENGLISH_FACETS = { values: { brand: { ჰოკო: 2 } }, labels: { brand: { ჰოკო: 'Hoco' } } };

  it("labels a brand by the English name the API sent, keeping the brand's own name as the value", () => {
    const [brand] = withFacetLabels([BRAND], ENGLISH_FACETS);

    expect(brand.optionLabels).toEqual({ ჰოკო: 'Hoco' });
    // The chip says Hoco; what it removes, and what the URL carries, is still ჰოკო.
    const [chip] = buildFilterChips({ brand: ['ჰოკო'] }, [brand]);
    expect(chip).toMatchObject({ label: 'Hoco', value: 'ჰოკო' });
  });

  it("lets the page's language win over a label the config already had", () => {
    const configured = { ...BRAND, optionLabels: { ჰოკო: 'ჰოკო (ჩინეთი)', Apple: 'Apple' } };

    const [brand] = withFacetLabels([configured], ENGLISH_FACETS);

    expect(brand.optionLabels).toEqual({ ჰოკო: 'Hoco', Apple: 'Apple' });
  });

  it('hands back the very same configs when there is nothing to label - a Georgian page', () => {
    const configs = [BRAND];

    expect(withFacetLabels(configs, { values: {}, labels: {} })).toBe(configs);
    expect(withFacetLabels(configs, { values: {} })).toBe(configs);
    expect(withFacetLabels(configs, null)).toBe(configs);
  });
});
