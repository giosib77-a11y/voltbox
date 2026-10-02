/**
 * The storefront's own JavaScript against the real API, in a real browser.
 *
 * What it does: drives the built site through one shopper's basket - add as a
 * guest, sign in, add more, sign out, sign in on another device - and fails if
 * the basket does not follow the account.
 * Where it fits: the e2e workflow, after backend/scripts/e2e/journey.py, which
 * leaves the products this buys. Needs the API on :8100 and the built site on
 * :4173, as that workflow brings them up.
 *
 * Why a browser at all: everything else stops short of the code a shopper
 * runs. vitest replaces fetch or the implementation behind api.js, and
 * journey.py checks the cart from Python with PUT /cart. From 8bb48c7 to
 * 1ebe26b api.js did not export mergeCart, saveCart or clearCart; the bundle
 * called `undefined`, swallowed the error, and every one of those checks
 * stayed green while no basket ever reached an account.
 *
 * Both languages, one after the other: Georgian at the shop's own paths, then
 * English under /en, each with a shopper of its own (registration is once per
 * address). The labels it looks for come from src/i18n/ka.json and en.json
 * through i18next, the way the page gets them, so a reworded string cannot
 * fail this and a page that shows the wrong language does. Pass `ka` or `en`
 * to walk one.
 *
 * The shopper arrives from an address of their own (X-Forwarded-For, which
 * uvicorn trusts from 127.0.0.1 by default). journey.py spends the
 * 5-a-minute sign-in allowance of 127.0.0.1 on purpose, and a second shopper
 * on another address is what the limit is meant to leave alone. The header is
 * added under the page, on the way out: set by the page's own requests it would
 * make every one of them need a CORS preflight, which the API refuses.
 */

import { readFileSync } from 'node:fs';

import i18next from 'i18next';
import { chromium } from 'playwright';

const ORIGIN = 'http://localhost:4173';
const API = 'http://127.0.0.1:8100/api/v1';
const SHOPPER_ADDRESS = '203.0.113.7';
const PASSWORD = 'Harbor-Lantern-58';

const translations = (language) =>
  JSON.parse(readFileSync(new URL(`../../src/i18n/${language}.json`, import.meta.url), 'utf8'));

await i18next.init({
  resources: { ka: { translation: translations('ka') }, en: { translation: translations('en') } },
  initAsync: false,
  interpolation: { escapeValue: false },
});

/** What differs per language: where the shop is, who shops, what it says. */
function walkFor(language) {
  return {
    language,
    shop: language === 'en' ? `${ORIGIN}/en` : ORIGIN,
    shopper: {
      email: language === 'en' ? 'basket-en@example.ge' : 'basket@example.ge',
      password: PASSWORD,
    },
    t: i18next.getFixedT(language),
  };
}

// Set per language by main().
let SHOP;
let SHOPPER;
let t;
// Past the cart's save debounce with room for a slow runner.
const WAIT_MS = 10_000;

const results = [];

function check(label, ok, detail = '') {
  results.push({ label, ok });
  process.stdout.write(`  [${ok ? 'OK  ' : 'FAIL'}] ${label}${detail ? `  -> ${detail}` : ''}\n`);
  return ok;
}

/** Resolves true when `promise` settles in time, false when it throws. */
async function happens(promise) {
  try {
    await promise;
    return true;
  } catch {
    return false;
  }
}

async function api(path, init = {}) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Forwarded-For': SHOPPER_ADDRESS,
      ...init.headers,
    },
  });
  if (!res.ok) throw new Error(`${init.method ?? 'GET'} ${path} -> ${res.status} ${await res.text()}`);
  return res.json();
}

const isCartCall = (method, path) => (res) =>
  res.request().method() === method && new URL(res.url()).pathname.endsWith(path) && res.ok();

async function signIn(page) {
  await page.goto(`${SHOP}/login`);
  // By autocomplete: the labels end in a required mark, and the password
  // label is also the start of the show-password button's name.
  await page.locator('input[autocomplete="email"]').fill(SHOPPER.email);
  await page.locator('input[autocomplete="current-password"]').fill(SHOPPER.password);
  const merged = page.waitForResponse(isCartCall('POST', '/cart/merge'), { timeout: WAIT_MS });
  await page.locator('form').getByRole('button', { name: t('nav.login'), exact: true }).click();
  return merged;
}

async function addToCart(page, product) {
  await page.goto(`${SHOP}/product/${product.slug}`);
  // The product's own button comes before the related products' ones.
  await page.getByRole('button', { name: t('common.addToCart') }).first().click();
}

const cartLink = (page, label) => page.getByRole('link', { name: label, exact: true });

async function walk(language) {
  ({ shop: SHOP, shopper: SHOPPER, t } = walkFor(language));
  process.stdout.write(`\n######## ${language}: ${SHOP} ########\n`);

  await api('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ ...SHOPPER, firstName: 'ანა', lastName: 'ბერიძე' }),
  });
  const listing = await api('/products?limit=12');
  const [first, second] = listing.items.filter((p) => p.inStock);
  if (!second) throw new Error('journey.py should have left two products in stock');

  const browser = await chromium.launch();
  const device = async () => {
    const context = await browser.newContext();
    await context.route('http://localhost:8100/**', (route) =>
      route.continue({
        headers: { ...route.request().headers(), 'x-forwarded-for': SHOPPER_ADDRESS },
      }),
    );
    return context;
  };
  try {
    process.stdout.write('\n=== 1. a guest fills a basket, then signs in ===\n');
    const laptop = await (await device()).newPage();
    await addToCart(laptop, first);
    check(
      `[${language}] the page is in ${language}`,
      (await laptop.locator('html').getAttribute('lang')) === language,
    );
    check(
      `[${language}] the guest basket holds it`,
      await happens(cartLink(laptop, t('cart.badge', { count: 1 })).waitFor({ timeout: WAIT_MS })),
    );
    check(
      `[${language}] signing in merges it into the account`,
      await happens(signIn(laptop)),
      'POST /cart/merge',
    );

    process.stdout.write('\n=== 2. signed in, they add more ===\n');
    const saved = laptop.waitForResponse(
      (res) => isCartCall('PUT', '/cart')(res) && res.request().postData()?.includes(second.id),
      { timeout: WAIT_MS },
    );
    await addToCart(laptop, second);
    check(`[${language}] the addition is saved to the account`, await happens(saved), 'PUT /cart');

    process.stdout.write('\n=== 3. they sign out ===\n');
    // From the header, on the page they are on. A reload first would merge
    // again, and a sign-out before that save came back rightly keeps the basket.
    await laptop.locator('header [aria-haspopup="menu"]').click();
    await laptop.getByRole('menuitem', { name: t('nav.logout'), exact: true }).click();
    check(
      `[${language}] the basket leaves this browser with them`,
      await happens(cartLink(laptop, t('cart.badgeEmpty')).waitFor({ timeout: WAIT_MS })),
      'kept only when the account never confirmed it',
    );

    process.stdout.write('\n=== 4. they sign in on another device ===\n');
    const phone = await (await device()).newPage();
    await happens(signIn(phone));
    check(
      `[${language}] the basket is waiting there`,
      await happens(cartLink(phone, t('cart.badge', { count: 2 })).waitFor({ timeout: WAIT_MS })),
    );
    await phone.goto(`${SHOP}/cart`);
    for (const product of [first, second]) {
      check(
        `[${language}] with ${product.name} in it`,
        await happens(
          phone.getByRole('main').getByText(product.name, { exact: true }).first().waitFor({ timeout: WAIT_MS }),
        ),
      );
    }
  } finally {
    await browser.close();
  }
}

async function main() {
  const asked = process.argv.slice(2);
  const languages = asked.length ? asked : ['ka', 'en'];
  for (const language of languages) {
    if (!['ka', 'en'].includes(language)) throw new Error(`unknown language: ${language}`);
    await walk(language);
  }

  const failed = results.filter((r) => !r.ok);
  process.stdout.write(`\n==== ${results.length - failed.length}/${results.length} passed ====\n`);
  for (const { label } of failed) process.stdout.write(`  FAILED: ${label}\n`);
  if (failed.length) process.exit(1);
}

await main();
