/**
 * Which texts load where: Georgian with the page, English only on /en, the
 * admin's error texts only with the admin code.
 *
 * What it covers: the module as a page load runs it - a fresh copy per test
 * (`vi.resetModules`) on a given address - and checks what is registered and
 * what the entry has to wait for. Why: all three used to be in the one bundle
 * every page downloads (A-047), and nothing about a test of `t` would notice
 * them coming back.
 * Notes: the module re-initialises the shared i18next, so this file keeps to
 * itself what it changes; setup's afterEach puts the language back to Georgian.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import en from './en.json';

function visit(path) {
  window.history.pushState({}, '', path);
}

async function freshModule() {
  vi.resetModules();
  return import('./index.js');
}

beforeEach(() => {
  vi.resetModules();
});

afterEach(() => {
  visit('/');
  vi.doUnmock('./en.json');
});

describe('on a Georgian page', () => {
  it('has no English texts and nothing to wait for', async () => {
    visit('/cart');
    const { i18n, t, languageReady } = await freshModule();

    expect(languageReady).toBeNull();
    expect(i18n.hasResourceBundle('en', 'translation')).toBe(false);
    expect(t('cart.title')).toBe('კალათა');
  });

  it('does not ask for the English chunk', async () => {
    visit('/');
    const loaded = vi.fn();
    vi.doMock('./en.json', () => {
      loaded();
      return { default: en };
    });

    await freshModule();
    await Promise.resolve();

    expect(loaded).not.toHaveBeenCalled();
  });
});

describe('on an English page', () => {
  it('waits for the English texts, and then answers in English', async () => {
    visit('/en/cart');
    const { i18n, t, languageReady } = await freshModule();

    expect(languageReady).toBeInstanceOf(Promise);
    await languageReady;

    expect(i18n.hasResourceBundle('en', 'translation')).toBe(true);
    expect(t('cart.title')).toBe(en.cart.title);
    expect(i18n.language).toBe('en');
  });

  it('shows Georgian, not keys, when the English chunk cannot be fetched', async () => {
    visit('/en');
    vi.doMock('./en.json', () => {
      throw new Error('chunk failed to load');
    });
    const { t, languageReady } = await freshModule();

    await expect(languageReady).rejects.toThrow();
    expect(t('cart.title')).toBe('კალათა');
  });

  it('can load the English texts again after a failure', async () => {
    visit('/en');
    let fail = true;
    vi.doMock('./en.json', () => {
      if (fail) throw new Error('offline');
      return { default: en };
    });
    const { loadEnglish, t, languageReady } = await freshModule();
    await expect(languageReady).rejects.toThrow();

    fail = false;
    await loadEnglish();

    expect(t('cart.title')).toBe(en.cart.title);
  });
});

describe('when the page mounts', () => {
  it('mounts at once on a Georgian page, before any promise settles', async () => {
    const { mountWhenReady } = await freshModule();
    const mount = vi.fn();

    mountWhenReady(mount, null);

    expect(mount).toHaveBeenCalledTimes(1);
  });

  it('waits for the English texts on an English page', async () => {
    const { mountWhenReady } = await freshModule();
    const mount = vi.fn();
    let arrive;

    mountWhenReady(mount, new Promise((resolve) => (arrive = resolve)));
    await Promise.resolve();
    expect(mount).not.toHaveBeenCalled();

    arrive();
    await vi.waitFor(() => expect(mount).toHaveBeenCalledTimes(1));
  });

  it('still mounts, once, when the English texts fail to load', async () => {
    const { mountWhenReady } = await freshModule();
    const mount = vi.fn();

    mountWhenReady(mount, Promise.reject(new Error('offline')));

    await vi.waitFor(() => expect(mount).toHaveBeenCalledTimes(1));
  });
});

describe('the admin error texts', () => {
  it('are not in the storefront until the admin code loads, then are', async () => {
    visit('/');
    const { i18n, t } = await freshModule();

    expect(i18n.exists('apiErrors.SKU_TAKEN')).toBe(false);
    expect(i18n.exists('apiErrors.INVALID_CREDENTIALS')).toBe(true);

    await import('../admin/adminApi.js');

    expect(t('apiErrors.SKU_TAKEN')).toBe('ეს SKU სხვა პროდუქტს უკვე უკავია.');
    // registering them takes nothing away
    expect(i18n.exists('apiErrors.INVALID_CREDENTIALS')).toBe(true);
  });
});
