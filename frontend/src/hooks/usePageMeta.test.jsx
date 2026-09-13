/**
 * Tests for the per-page meta tags.
 *
 * What they cover: that a page writes its own description, canonical link and
 * structured data, and - the part that actually breaks - that it takes them
 * back down when it unmounts. A description left behind by the previous page
 * describes the wrong thing, and two Product blocks on one page is how a shop
 * ends up with the wrong price in a search result.
 *
 * What they do not cover: link previews. Facebook and Messenger do not run
 * JavaScript, so none of this reaches them; the static tags in index.html are
 * what they see.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';

import usePageMeta, { productStructuredData } from './usePageMeta.js';
import { SITE_DESCRIPTION } from '../constants/index.js';

const PRODUCT = {
  id: 'p1',
  slug: 'galaxy-a55',
  name: 'Galaxy A55',
  sku: 'SM-A556',
  shortDescription: 'ხუთი მეტრი ჩარჯერით',
  price: 1299,
  inStock: true,
  brand: 'Samsung',
  images: ['/a.png', '/b.png'],
};

function Page({ meta }) {
  usePageMeta(meta);
  return <div>page</div>;
}

const description = () => document.head.querySelector('meta[name="description"]')?.content;
const canonical = () => document.head.querySelector('link[rel="canonical"]')?.getAttribute('href');
const jsonLd = () => {
  const tag = document.head.querySelector('script[type="application/ld+json"]');
  return tag ? JSON.parse(tag.textContent) : null;
};

beforeEach(() => {
  document.head.innerHTML = '';
});

afterEach(() => {
  document.head.innerHTML = '';
});

describe('usePageMeta', () => {
  it('writes the page description', () => {
    render(<Page meta={{ description: 'ხუთი მეტრი ჩარჯერით' }} />);

    expect(description()).toBe('ხუთი მეტრი ჩარჯერით');
  });

  it('falls back to the site description rather than leaving none', () => {
    render(<Page meta={{}} />);

    expect(description()).toBe(SITE_DESCRIPTION);
  });

  it('restores the previous description when the page goes away', () => {
    // index.html ships one for the whole site. A page that deleted it on the
    // way out would leave the next one with nothing at all.
    document.head.innerHTML = '<meta name="description" content="საიტის აღწერა" />';
    const { unmount } = render(<Page meta={{ description: 'გვერდის აღწერა' }} />);
    expect(description()).toBe('გვერდის აღწერა');

    unmount();

    expect(description()).toBe('საიტის აღწერა');
  });

  it('writes a canonical link for the page', () => {
    render(<Page meta={{ canonical: '/product/galaxy-a55' }} />);

    expect(canonical()).toMatch(/\/product\/galaxy-a55$/);
  });

  it('never leaves one page canonical pointing at another', () => {
    const { unmount } = render(<Page meta={{ canonical: '/product/one' }} />);
    unmount();

    expect(canonical()).toBeUndefined();
  });

  it('adds exactly one structured-data block', () => {
    render(<Page meta={{ structuredData: productStructuredData(PRODUCT) }} />);

    expect(document.head.querySelectorAll('script[type="application/ld+json"]')).toHaveLength(1);
    expect(jsonLd()['@type']).toBe('Product');
  });

  it('replaces it rather than stacking a second one', () => {
    const { rerender } = render(<Page meta={{ structuredData: productStructuredData(PRODUCT) }} />);
    rerender(
      <Page
        meta={{ structuredData: productStructuredData({ ...PRODUCT, name: 'Galaxy A56' }) }}
      />,
    );

    expect(document.head.querySelectorAll('script[type="application/ld+json"]')).toHaveLength(1);
    expect(jsonLd().name).toBe('Galaxy A56');
  });
});

describe('productStructuredData', () => {
  it('describes the product the way schema.org does', () => {
    const data = productStructuredData(PRODUCT);

    expect(data['@type']).toBe('Product');
    expect(data.name).toBe('Galaxy A55');
    expect(data.sku).toBe('SM-A556');
    expect(data.brand).toEqual({ '@type': 'Brand', name: 'Samsung' });
  });

  it('states the price as text, never as a float', () => {
    // A search result shows this number. 1299.1 arriving as 1299.0999999 is
    // the kind of thing that only shows up in public.
    const data = productStructuredData({ ...PRODUCT, price: '1299.10' });

    expect(data.offers.price).toBe('1299.10');
    expect(data.offers.priceCurrency).toBe('GEL');
  });

  it('does not promise stock it does not have', () => {
    // Google prints "In stock" beside the result. Getting this wrong brings
    // somebody to the shop to be disappointed.
    const data = productStructuredData({ ...PRODUCT, inStock: false });

    expect(data.offers.availability).toBe('https://schema.org/OutOfStock');
  });

  it('says nothing at all when there is no product', () => {
    expect(productStructuredData(null)).toBeNull();
  });
});
