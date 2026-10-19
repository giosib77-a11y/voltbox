/**
 * Every storefront page, in both themes at two widths, as pictures.
 *
 * What it does: drives the built mock-mode site through one shopper's visit -
 * browsing, a basket, registering and signing in through the forms, placing an
 * order - and writes a full-page screenshot of every route, light and dark,
 * at 1440x900 and 390x844 (the mobile menu at 390 only, the category flyout at
 * 1440 only). It also shoots design-reference/Site.dc.html, the mockup the
 * redesign follows, in both of its themes at 1440, so a page and its mockup
 * sit side by side.
 * Where it fits: a look-and-check pass by hand, before and after restyling.
 * Not part of CI: it needs a browser and writes pictures a person looks at.
 * Besides the pictures it fails (exit 1, one line per problem) on what a
 * picture cannot show: a console error, a request that failed or came back 4xx
 * or 5xx (a font that 404s), a request to any host but localhost, and a page
 * wider than its viewport (sideways scroll).
 *
 * Output: frontend/test-results/screens/<theme>-<width>-<name>.png and
 * mockup-<theme>-1440.png. The root .gitignore's `test-results/` has no
 * leading slash, so it covers frontend/test-results too.
 *
 * How to run (from frontend/):
 *   VITE_API_MODE=mock npm run build
 *   npm run preview                     # :4173, leave it running
 *   node scripts/e2e/screens.mjs        # everything
 *   node scripts/e2e/screens.mjs home cart mockup   # only these routes
 * Route names are the ones in ROUTES below, plus `mockup`.
 * Another preview or output folder: SCREENS_ORIGIN and SCREENS_DIR (below).
 *
 * The theme is the shopper's pick, written to localStorage['theme:v1'] as JSON
 * ('"dark"') before the page loads - what src/utils/theme.js and
 * public/theme-init.js read. Motion is switched off (reduced motion) so a
 * transition is never caught half-way.
 *
 * The mockup is the one place a third-party host is allowed: it loads Google
 * Fonts, and the "no third-party request" rule is about the site's own pages.
 * Its fonts are part of how it looks, so they are let through; its requests
 * are not checked, and offline it falls back to system fonts.
 *
 * Elements are found by role and by the names in src/i18n/ka.json (read the
 * way cart-sync.mjs does), by form field id or autocomplete, and by href - not
 * by class or text - so a restyle does not break the walk. The two things
 * that are not a role: the skeleton wait looks for a "shimmer" class and gives
 * up quietly, and the mockup's switch is found by its aria-label ending in
 * "რეჟიმი".
 */

import { createReadStream, mkdirSync, readFileSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

import i18next from 'i18next';
import { chromium } from 'playwright';

import { categories } from '../../src/data/categories.js';
import { products } from '../../src/data/products.js';

// Two runs side by side (two tasks at once) each need their own preview and
// folder: SCREENS_ORIGIN=http://localhost:4174 SCREENS_DIR=screens-b.
const ORIGIN = process.env.SCREENS_ORIGIN || 'http://localhost:4173';
const OUT = fileURLToPath(
  new URL(`../../test-results/${process.env.SCREENS_DIR || 'screens'}/`, import.meta.url),
);
const MOCKUP_DIR = fileURLToPath(new URL('../../../design-reference/', import.meta.url));
const THEME_KEY = 'theme:v1';
const THEMES = ['light', 'dark'];
const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
];
const WAIT_MS = 15_000;

const SHOPPER = { firstName: 'ანა', lastName: 'ბერიძე', email: 'screens@example.ge', password: 'Harbor-Lantern-58' };

i18next.init({
  resources: {
    ka: {
      translation: JSON.parse(readFileSync(new URL('../../src/i18n/ka.json', import.meta.url), 'utf8')),
    },
  },
  lng: 'ka',
  initAsync: false,
  interpolation: { escapeValue: false },
});
const t = i18next.getFixedT('ka');

const [firstCategory] = categories;
const [firstProduct, secondProduct] = products.filter((p) => p.stock > 0);

/* -------------------------------------------------------------------------- */
/*  Steps a route may need first                                              */
/* -------------------------------------------------------------------------- */

const fillById = (page, id, value) => page.locator(`#${id}`).fill(value);

/** Register through the form, drop that session, sign in through the login form. */
async function ensureUser(s) {
  if (s.signedIn) return;
  const { page } = s;
  const leftTheForm = (path) => page.waitForURL((url) => url.pathname !== path, { timeout: WAIT_MS });
  await page.goto(`${ORIGIN}/register`);
  await page.locator('input[autocomplete="given-name"]').fill(SHOPPER.firstName);
  await page.locator('input[autocomplete="family-name"]').fill(SHOPPER.lastName);
  await page.locator('input[autocomplete="email"]').fill(SHOPPER.email);
  await page.locator('input[autocomplete="new-password"]').nth(0).fill(SHOPPER.password);
  await page.locator('input[autocomplete="new-password"]').nth(1).fill(SHOPPER.password);
  await page.locator('form button[type="submit"]').click();
  await leftTheForm('/register');
  // Registering signs in; the login form is the one to try, so end that session.
  await page.evaluate(() => window.localStorage.removeItem('auth:v1'));
  await page.goto(`${ORIGIN}/login`);
  await page.locator('input[autocomplete="email"]').fill(SHOPPER.email);
  await page.locator('input[autocomplete="current-password"]').fill(SHOPPER.password);
  await page.locator('form button[type="submit"]').click();
  await leftTheForm('/login');
  s.signedIn = true;
}

/** Two different products in the basket, added the way a shopper does. */
async function ensureCart(s) {
  if (s.cartLines === 2) return;
  const { page } = s;
  for (const [index, product] of [firstProduct, secondProduct].entries()) {
    await page.goto(`${ORIGIN}/product/${product.slug}`);
    // The product's own button comes before the related products' ones.
    await page.getByRole('button', { name: t('common.addToCart') }).first().click();
    await page
      .getByRole('link', { name: t('cart.badge', { count: index + 1 }), exact: true })
      .waitFor({ timeout: WAIT_MS });
  }
  s.cartLines = 2;
}

async function placeOrder(s) {
  const { page } = s;
  await ensureUser(s);
  await ensureCart(s);
  await page.goto(`${ORIGIN}/checkout`);
  await fillById(page, 'checkout-firstName', SHOPPER.firstName);
  await fillById(page, 'checkout-lastName', SHOPPER.lastName);
  await fillById(page, 'checkout-phone', '555123456');
  // The first city of the delivery rules; index 0 is the placeholder.
  await page.locator('#checkout-city').selectOption({ index: 1 });
  await fillById(page, 'checkout-address', 'რუსთაველის გამზ. 12');
  await page.getByRole('button', { name: t('checkout.confirm') }).click();
  await page.waitForURL(/\/checkout\/success\//, { timeout: WAIT_MS });
  s.cartLines = 0;
}

/* -------------------------------------------------------------------------- */
/*  The routes, in the order a visit goes                                     */
/* -------------------------------------------------------------------------- */

/** `prepare` leaves the page as it should be shot; `only` limits it to one width. */
const at = (path) => async ({ page }) => {
  await page.goto(`${ORIGIN}${path}`);
};
const asUser = (path) => async (s) => {
  await ensureUser(s);
  await s.page.goto(`${ORIGIN}${path}`);
};

const ROUTES = [
  { name: 'home', prepare: at('/') },
  { name: 'category', prepare: at(`/category/${firstCategory.slug}`) },
  { name: 'product', prepare: at(`/product/${firstProduct.slug}`) },
  {
    name: 'search',
    prepare: at(`/search?q=${encodeURIComponent(firstProduct.name.split(' ')[0])}`),
  },
  { name: 'search-none', prepare: at('/search?q=zzzqqxx') },
  { name: 'cart-empty', prepare: at('/cart') },
  {
    name: 'cart',
    prepare: async (s) => {
      await ensureCart(s);
      await s.page.goto(`${ORIGIN}/cart`);
    },
  },
  {
    name: 'checkout',
    prepare: async (s) => {
      await ensureCart(s);
      await s.page.goto(`${ORIGIN}/checkout`);
    },
  },
  { name: 'login', prepare: at('/login') },
  { name: 'register', prepare: at('/register') },
  { name: 'forgot-password', prepare: at('/forgot-password') },
  { name: 'reset-password', prepare: at('/reset-password?token=screens-token') },
  { name: 'delivery', prepare: at('/delivery') },
  { name: 'returns', prepare: at('/returns') },
  { name: 'privacy', prepare: at('/privacy') },
  { name: 'faq', prepare: at('/faq') },
  { name: 'not-found', prepare: at('/no-such-page') },
  { name: 'en-home', prepare: at('/en/') },
  { name: 'success', prepare: placeOrder },
  { name: 'orders', prepare: asUser('/account/orders') },
  { name: 'profile', prepare: asUser('/account/profile') },
  { name: 'addresses', prepare: asUser('/account/addresses') },
  { name: 'password', prepare: asUser('/account/password') },
  {
    name: 'mobile-menu',
    only: 390,
    prepare: async ({ page }) => {
      await page.goto(`${ORIGIN}/`);
      await page.getByRole('button', { name: t('header.openMenu') }).click();
      await page.getByRole('dialog').waitFor({ timeout: WAIT_MS });
    },
  },
  {
    name: 'category-flyout',
    only: 1440,
    prepare: async ({ page }) => {
      await page.goto(`${ORIGIN}/`);
      await page.getByRole('button', { name: t('nav.categories'), exact: true }).first().click();
      await page.locator('button[aria-expanded="true"][aria-controls]').first().waitFor({ timeout: WAIT_MS });
    },
  },
];

/* -------------------------------------------------------------------------- */
/*  Findings and pictures                                                     */
/* -------------------------------------------------------------------------- */

const findings = new Set();
let shots = 0;

/** Watches one page; what it sees is filed under whatever `label.current` is. */
function watch(page, label) {
  const report = (what) => findings.add(`[${label.current}] ${what}`);
  page.on('console', (msg) => {
    if (msg.type() === 'error') report(`console error: ${msg.text()} (${msg.location().url})`);
  });
  page.on('pageerror', (error) => report(`uncaught error: ${error.message}`));
  page.on('requestfailed', (request) => {
    // A navigation that a later one replaced is not a failure of the page.
    if (request.failure()?.errorText === 'net::ERR_ABORTED') return;
    report(`request failed: ${request.url()} (${request.failure()?.errorText})`);
  });
  page.on('response', (response) => {
    if (response.status() >= 400) report(`HTTP ${response.status()}: ${response.url()}`);
    // The preview answers a missing file with index.html and a 200, so a font
    // that is gone arrives as a "successful" page of HTML.
    const type = response.request().resourceType();
    const contentType = response.headers()['content-type'] ?? '';
    if (['font', 'image', 'script', 'stylesheet'].includes(type) && contentType.startsWith('text/html')) {
      report(`${type} answered with HTML (missing file?): ${response.url()}`);
    }
  });
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (['http:', 'https:'].includes(url.protocol) && url.hostname !== 'localhost') {
      report(`request to another host: ${request.url()}`);
    }
  });
}

/** Skeletons gone, fonts and images in, lazy images scrolled into view. */
async function settle(page) {
  await page.waitForLoadState('load');
  await page.waitForLoadState('networkidle').catch(() => {});
  await page
    .waitForFunction(() => !document.querySelector('[class*="shimmer"]'), null, { timeout: 5000 })
    .catch(() => {});
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 60));
    }
    window.scrollTo(0, 0);
    await document.fonts.ready;
  });
  await page
    .waitForFunction(() => [...document.images].every((img) => img.complete), null, { timeout: 5000 })
    .catch(() => {});
  await page.waitForTimeout(250);
}

async function shoot(page, file) {
  await page.screenshot({ path: join(OUT, file), fullPage: true });
  shots += 1;
}

async function walkSite(browser, wanted) {
  for (const theme of THEMES) {
    for (const viewport of VIEWPORTS) {
      const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
      await context.addInitScript(
        ([key, value]) => {
          try {
            window.localStorage.setItem(key, value);
          } catch {
            // storage refused: the site then follows the system setting
          }
        },
        [THEME_KEY, JSON.stringify(theme)],
      );
      const page = await context.newPage();
      const label = { current: `${theme}-${viewport.width}` };
      watch(page, label);
      const state = { page, signedIn: false, cartLines: 0 };
      try {
        for (const route of ROUTES) {
          if (!wanted.has(route.name) || (route.only && route.only !== viewport.width)) continue;
          label.current = `${theme}-${viewport.width}-${route.name}`;
          try {
            await route.prepare(state);
            await settle(page);
            const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
            if (scrollWidth > viewport.width) {
              findings.add(`[${label.current}] page is ${scrollWidth}px wide in a ${viewport.width}px viewport`);
            }
            await shoot(page, `${label.current}.png`);
          } catch (error) {
            findings.add(`[${label.current}] could not be shot: ${String(error.message).split('\n')[0]}`);
          }
        }
      } finally {
        await context.close();
      }
    }
  }
}

/* -------------------------------------------------------------------------- */
/*  The mockup                                                                */
/* -------------------------------------------------------------------------- */

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8' };

/** design-reference/ over HTTP (its scripts do not load from file://). */
function serveMockup() {
  const server = createServer((req, res) => {
    const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^([/\\])+/, '');
    const file = join(MOCKUP_DIR, path);
    try {
      if (!file.startsWith(MOCKUP_DIR) || !statSync(file).isFile()) throw new Error('not a file');
    } catch {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream' });
    createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(0, 'localhost', () => resolve(server)));
}

async function walkMockup(browser) {
  const server = await serveMockup();
  const context = await browser.newContext({ viewport: VIEWPORTS[0], reducedMotion: 'reduce' });
  try {
    const page = await context.newPage();
    await page.goto(`http://localhost:${server.address().port}/Site.dc.html`);
    for (const theme of THEMES) {
      if (theme === 'dark') await page.locator('button[aria-label$="რეჟიმი"]').click();
      await settle(page);
      await shoot(page, `mockup-${theme}-1440.png`);
    }
  } catch (error) {
    findings.add(`[mockup] could not be shot: ${String(error.message).split('\n')[0]}`);
  } finally {
    await context.close();
    server.close();
  }
}

/* -------------------------------------------------------------------------- */

async function main() {
  const names = [...ROUTES.map((r) => r.name), 'mockup'];
  const asked = process.argv.slice(2);
  const unknown = asked.filter((name) => !names.includes(name));
  if (unknown.length) throw new Error(`unknown route: ${unknown.join(', ')} (one of ${names.join(', ')})`);
  const wanted = new Set(asked.length ? asked : names);

  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  try {
    await walkSite(browser, wanted);
    if (wanted.has('mockup')) await walkMockup(browser);
  } finally {
    await browser.close();
  }

  process.stdout.write(`${shots} screenshots in ${OUT}\n`);
  for (const finding of findings) process.stdout.write(`PROBLEM ${finding}\n`);
  if (findings.size) process.exit(1);
}

await main();
