/**
 * The storefront's language: which one, where it comes from, and its words.
 *
 * What it does: reads the language from the address - Georgian at today's
 * paths, English under /en - and sets up i18next with that one language for
 * the life of the page.
 * Where it fits: imported first by main.jsx, so every module after it can call
 * `t`; App.jsx mounts the router under `basename(language)`.
 *
 * Why the language never changes while a page is open: the switch is a plain
 * link to the same page in the other language, and following it loads the
 * page again. That is what lets the router's basename carry the language -
 * every Link, navigate() and <Navigate> in the shop stays in it without being
 * told - and lets code outside React (httpClient's error messages, the
 * validators) translate with a plain `t` and nothing to subscribe to.
 *
 * The admin panel lives at /admin and is always Georgian: /en/admin is not a
 * route, and an English page links to the panel with a full load.
 */

import i18next from 'i18next';

import ka from './ka.json';
import en from './en.json';

export const DEFAULT_LANGUAGE = 'ka';
export const LANGUAGES = ['ka', 'en'];

/** What each language puts in front of a path. Georgian keeps the bare one. */
const PREFIX = { ka: '', en: '/en' };

const EN_PATH = /^\/en(?=\/|$)/;

/** `/en/cart` → 'en'; `/cart`, `/english` → 'ka'. */
export function languageFromPath(pathname) {
  return EN_PATH.test(pathname || '') ? 'en' : DEFAULT_LANGUAGE;
}

/** The router's basename for a language: '' for Georgian, '/en' for English. */
export function basename(language) {
  return PREFIX[language] ?? '';
}

/** `/en/cart` → `/cart`. A path with no language prefix comes back as it is. */
export function stripLanguage(pathname) {
  return (pathname || '/').replace(EN_PATH, '') || '/';
}

/**
 * A path as it reads in `language`: ('/cart', 'en') → '/en/cart'.
 * The English home page is `/en`, not `/en/` - one address per page.
 */
export function localizedPath(path, language) {
  const prefix = basename(language);
  if (!prefix) return path || '/';
  return !path || path === '/' ? prefix : `${prefix}${path}`;
}

// The language of the page that is open. Fixed until the next page load;
// everything else asks `currentLanguage()`, which a test can switch.
const pageLanguage = languageFromPath(globalThis.location?.pathname);

i18next.init({
  lng: pageLanguage,
  // A key missing in English shows the Georgian rather than the key itself.
  // i18n.test.js keeps the two files in step, so this is a backstop.
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: LANGUAGES,
  resources: { ka: { translation: ka }, en: { translation: en } },
  // Resources are bundled, so there is nothing to wait for: `t` works the
  // moment this module has run.
  initAsync: false,
  // React escapes what it renders; escaping here as well would show &amp;.
  interpolation: { escapeValue: false },
  returnNull: false,
});

/**
 * The tags index.html ships, made true for an English page before anything
 * renders: the document's language, and the canonical and og:url that name the
 * home page - `/en` on an English page. A page with its own canonical replaces
 * it and restores this one on leaving (usePageMeta.js).
 */
function localizeStaticHead(language) {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = language;
  if (language === DEFAULT_LANGUAGE) return;

  const localize = (element, attribute) => {
    const value = element?.getAttribute(attribute);
    if (!value) return;
    try {
      const url = new URL(value);
      url.pathname = localizedPath(url.pathname, language);
      element.setAttribute(attribute, url.href);
    } catch {
      // not an absolute URL - nothing a crawler could use either way
    }
  };
  localize(document.head.querySelector('link[rel="canonical"]'), 'href');
  localize(document.head.querySelector('meta[property="og:url"]'), 'content');
  document.head.querySelector('meta[property="og:locale"]')?.setAttribute('content', 'en_US');
}

localizeStaticHead(pageLanguage);

export const i18n = i18next;

/** Translate a key. Bound, so it can be passed around and imported by name. */
export const t = (key, options) => i18next.t(key, options);

/**
 * Georgian, whatever the page's language. For the info pages, whose text has
 * not been translated: a sentence on them stays whole in Georgian rather than
 * taking an English fragment - a delivery time, a page title - in the middle.
 */
export const tKa = (key, options) => i18next.getFixedT(DEFAULT_LANGUAGE)(key, options);

/** The language `t` is answering in - the page's, or a test's override. */
export function currentLanguage() {
  return i18next.language || DEFAULT_LANGUAGE;
}
