import { mkdtemp, readFile, rm, copyFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import process from 'node:process';
import { afterEach, describe, expect, it } from 'vitest';
import { englishPreload } from '../../vite-plugins/englishPreload.js';
import { languageFromPath } from './index.js';

const EN_FILE = 'assets/en-AbC123.js';

const bundle = (overrides = {}) => ({
  'assets/index-1.js': {
    type: 'chunk',
    isEntry: true,
    fileName: 'assets/index-1.js',
    moduleIds: ['D:\\app\\src\\main.jsx', 'D:\\app\\src\\i18n\\ka.json'],
  },
  [EN_FILE]: {
    type: 'chunk',
    isEntry: false,
    fileName: EN_FILE,
    moduleIds: ['D:\\app\\src\\i18n\\en.json'],
  },
  ...overrides,
});

const dirs = [];
afterEach(async () => {
  document.head.innerHTML = '';
  await Promise.all(dirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })));
});

/** Runs the plugin's build hooks over a copy of the real public/theme-init.js. */
async function build(fakeBundle = bundle(), base = '/') {
  const dir = await mkdtemp(join(tmpdir(), 'voltbox-preload-'));
  dirs.push(dir);
  await copyFile(join(process.cwd(), 'public', 'theme-init.js'), join(dir, 'theme-init.js'));
  const plugin = englishPreload();
  plugin.configResolved({ base });
  plugin.generateBundle.call({ error: (message) => { throw new Error(message); } }, {}, fakeBundle);
  await plugin.writeBundle({ dir });
  return readFile(join(dir, 'theme-init.js'), 'utf8');
}

/** One page load at `path`: the built head script, then the links it left. */
function load(source, path) {
  document.head.innerHTML = '';
  window.history.replaceState({}, '', path);
  new Function(source)();
  return [...document.head.querySelectorAll('link[rel="modulepreload"]')].map((link) =>
    link.getAttribute('href'),
  );
}

describe('the English modulepreload', () => {
  it('adds exactly one preload for the English chunk on /en pages', async () => {
    const source = await build();
    expect(load(source, '/en')).toEqual(['/' + EN_FILE]);
    expect(load(source, '/en/cart')).toEqual(['/' + EN_FILE]);
  });

  it('adds nothing on Georgian pages, the admin panel or look-alike paths', async () => {
    const source = await build();
    for (const path of ['/', '/cart', '/english', '/entry', '/admin', '/admin/en']) {
      expect(load(source, path)).toEqual([]);
    }
  });

  it('agrees with languageFromPath on which paths are English', async () => {
    const source = await build();
    for (const path of ['/', '/en', '/en/', '/en/cart', '/english', '/ken', '/admin', '/cart/en']) {
      expect(load(source, path).length === 1).toBe(languageFromPath(path) === 'en');
    }
  });

  it('keeps the theme script working', async () => {
    const source = await build();
    document.documentElement.className = '';
    window.history.replaceState({}, '', '/en');
    new Function(source)();
    expect(document.documentElement.className).toMatch(/^theme-(light|dark)$/);
  });

  it('honours a non-root base', async () => {
    expect(load(await build(bundle(), '/shop/'), '/en')).toEqual(['/shop/' + EN_FILE]);
  });

  it('finds the chunk by its module, not by its name', async () => {
    const renamed = bundle();
    delete renamed[EN_FILE];
    renamed['assets/lang-9.js'] = {
      type: 'chunk',
      isEntry: false,
      fileName: 'assets/lang-9.js',
      moduleIds: ['/app/src/i18n/en.json'],
    };
    expect(load(await build(renamed), '/en')).toEqual(['/assets/lang-9.js']);
  });

  it('fails the build when the English chunk is missing', async () => {
    const without = bundle();
    delete without[EN_FILE];
    await expect(build(without)).rejects.toThrow(/English chunk/);
  });

  it('fails the build when theme-init.js was not copied', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'voltbox-preload-'));
    dirs.push(dir);
    const plugin = englishPreload();
    plugin.configResolved({ base: '/' });
    plugin.generateBundle.call({ error: () => {} }, {}, bundle());
    await expect(plugin.writeBundle({ dir })).rejects.toThrow();
  });
});
