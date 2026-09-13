import { useEffect } from 'react';

import { SITE_DESCRIPTION, SITE_NAME } from '../constants/index.js';

/**
 * გვერდის meta-ტეგები: აღწერა, canonical და სტრუქტურირებული მონაცემები.
 *
 * What it does: writes the tags a search engine reads per page, and removes
 * them again when the page unmounts so the next one does not inherit them.
 * Where it fits: called by the pages that have something specific to say —
 * a product, a category. `useDocumentTitle` stays separate; it is used
 * everywhere and has nothing to clean up.
 *
 * What it deliberately does not do: help a link preview. Facebook, Messenger
 * and Viber do not run JavaScript, so anything written here is invisible to
 * them — they see the static tags in index.html and nothing else. Google does
 * render the page, which is why the description and the JSON-LD below are
 * worth writing at all.
 */

const SITE_URL = (import.meta.env?.VITE_SITE_URL || '').replace(/\/+$/, '');
const JSON_LD_ID = 'voltbox-structured-data';

function setMeta(name, content) {
  if (!content) return null;
  let tag = document.head.querySelector(`meta[name="${name}"]`);
  const created = !tag;
  if (!tag) {
    tag = document.createElement('meta');
    tag.setAttribute('name', name);
    document.head.appendChild(tag);
  }
  const previous = tag.getAttribute('content');
  tag.setAttribute('content', content);
  // Restores what was there rather than deleting: index.html ships a
  // site-wide description, and leaving a page without one is worse than
  // leaving the general one.
  return () => {
    if (created) tag.remove();
    else if (previous !== null) tag.setAttribute('content', previous);
  };
}

function setCanonical(path) {
  if (!path) return null;
  let tag = document.head.querySelector('link[rel="canonical"]');
  const created = !tag;
  if (!tag) {
    tag = document.createElement('link');
    tag.setAttribute('rel', 'canonical');
    document.head.appendChild(tag);
  }
  const previous = tag.getAttribute('href');
  tag.setAttribute('href', `${SITE_URL}${path}`);
  return () => {
    if (created) tag.remove();
    else if (previous !== null) tag.setAttribute('href', previous);
  };
}

function setStructuredData(data) {
  if (!data) return null;
  const script = document.createElement('script');
  script.type = 'application/ld+json';
  script.id = JSON_LD_ID;
  script.textContent = JSON.stringify(data);
  // One block per page. Two Product blocks on one page is how a shop ends up
  // with the wrong price in a search result.
  document.getElementById(JSON_LD_ID)?.remove();
  document.head.appendChild(script);
  return () => script.remove();
}

export function usePageMeta({ description, canonical, structuredData } = {}) {
  const serialized = structuredData ? JSON.stringify(structuredData) : null;

  useEffect(() => {
    const undo = [
      setMeta('description', description || SITE_DESCRIPTION),
      setCanonical(canonical),
      setStructuredData(serialized ? JSON.parse(serialized) : null),
    ].filter(Boolean);

    return () => undo.forEach((restore) => restore());
  }, [description, canonical, serialized]);
}

/**
 * A product as schema.org describes one.
 *
 * `availability` and `price` are the two fields Google shows beside a result.
 * Getting them wrong is worse than leaving them out — a result promising
 * "In stock" for something that is not brings somebody to the shop to be
 * disappointed, so both come from the same data the page renders.
 */
export function productStructuredData(product) {
  if (!product) return null;

  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.name,
    description: product.shortDescription || product.description || undefined,
    sku: product.sku || undefined,
    image: product.images?.length ? product.images : undefined,
    brand: product.brand ? { '@type': 'Brand', name: product.brand } : undefined,
    offers: {
      '@type': 'Offer',
      priceCurrency: 'GEL',
      price: String(product.price),
      availability: product.inStock
        ? 'https://schema.org/InStock'
        : 'https://schema.org/OutOfStock',
      url: SITE_URL && product.slug ? `${SITE_URL}/product/${product.slug}` : undefined,
      seller: { '@type': 'Organization', name: SITE_NAME },
    },
  };
}

export default usePageMeta;
