import { useEffect } from 'react';

import { SITE_NAME } from '../constants/index.js';
import { DEFAULT_LANGUAGE, LANGUAGES, currentLanguage, localizedPath, t } from '../i18n/index.js';

/**
 * გვერდის meta-ტეგები: აღწერა, canonical და სტრუქტურირებული მონაცემები.
 *
 * What it does: writes the tags a search engine reads per page, and removes
 * them again when the page unmounts so the next one does not inherit them.
 * Where it fits: called by the pages that have something specific to say —
 * a product, a category. `useDocumentTitle` stays separate; it is used
 * everywhere and has nothing to clean up. `useLanguageAlternates`, below, is
 * the Layout's: every page names its other-language version.
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
  // The page's own address in the language it is in: `/en/product/x` is its
  // own page, not a copy of `/product/x`, or the hreflang pair means nothing.
  const href = `${SITE_URL}${localizedPath(path, currentLanguage())}`;
  let tag = document.head.querySelector('link[rel="canonical"]');
  const created = !tag;
  if (!tag) {
    tag = document.createElement('link');
    tag.setAttribute('rel', 'canonical');
    document.head.appendChild(tag);
  }
  const previous = tag.getAttribute('href');
  tag.setAttribute('href', href);
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
      setMeta('description', description || t('site.description')),
      setCanonical(canonical),
      setStructuredData(serialized ? JSON.parse(serialized) : null),
    ].filter(Boolean);

    return () => undo.forEach((restore) => restore());
  }, [description, canonical, serialized]);
}

/**
 * The page in every language, as `<link rel="alternate" hreflang>`.
 *
 * `pathname` is the router's, without the language: `/cart` on both `/cart`
 * and `/en/cart`. Each page lists both languages and itself among them, which
 * is what a search engine needs to treat the two as one page in two languages
 * rather than as duplicates; x-default is the Georgian, the shop's own.
 *
 * And `<html lang>`, which the page load already set (i18n/index.js): set
 * again here so it can never disagree with the words on the page.
 */
export function useLanguageAlternates(pathname) {
  useEffect(() => {
    document.documentElement.lang = currentLanguage();

    const links = [
      ...LANGUAGES.map((language) => [language, localizedPath(pathname, language)]),
      ['x-default', localizedPath(pathname, DEFAULT_LANGUAGE)],
    ].map(([hreflang, path]) => {
      const link = document.createElement('link');
      link.setAttribute('rel', 'alternate');
      link.setAttribute('hreflang', hreflang);
      link.setAttribute('href', `${SITE_URL}${path}`);
      document.head.appendChild(link);
      return link;
    });

    return () => links.forEach((link) => link.remove());
  }, [pathname]);
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
      url:
        SITE_URL && product.slug
          ? `${SITE_URL}${localizedPath(`/product/${product.slug}`, currentLanguage())}`
          : undefined,
      seller: { '@type': 'Organization', name: SITE_NAME },
    },
  };
}

export default usePageMeta;
