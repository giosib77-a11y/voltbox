import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

/**
 * Starts the English chunk's download from <head> on an English page.
 *
 * Without it, `en-*.js` is requested only once the entry has run
 * (`loadEnglish()` in src/i18n/index.js), and main.jsx renders after it: an
 * English page pays one more round trip before its first render. A modulepreload
 * puts that request beside the entry's.
 *
 * Why it lives in theme-init.js: the chunk's hashed name exists only after the
 * build, and the CSP (`script-src 'self'`, render.yaml) forbids an inline
 * script. theme-init.js is the classic script every page already loads first in
 * <head>, so a few bytes appended to it add no request. A static
 * <link rel="modulepreload"> in index.html would be on Georgian pages too, and
 * they must carry no English bytes. The appended code does nothing off `/en`.
 *
 * The file is appended to in `dist/` after Vite has copied `public/`, not in
 * `public/`: dev server and tests have no chunk name and preload nothing.
 */

// The English chunk is found by the module inside it, not by a guessed name.
const EN_JSON = /[\\/]i18n[\\/]en\.json$/;

/** The path rule of languageFromPath() in src/i18n/index.js (EN_PATH). */
export function preloadSnippet(href) {
  return (
    '\n/* English page: fetch its texts beside the entry (vite-plugins/englishPreload.js). */\n' +
    '(function () {\n' +
    "  if (!/^\\/en(\\/|$)/.test(window.location.pathname)) return;\n" +
    "  var link = document.createElement('link');\n" +
    "  link.rel = 'modulepreload';\n" +
    `  link.href = ${JSON.stringify(href)};\n` +
    '  document.head.appendChild(link);\n' +
    '})();\n'
  );
}

export function englishPreload() {
  let base = '/';
  let href = null;
  return {
    name: 'voltbox-english-preload',
    apply: 'build',
    configResolved(config) {
      base = config.base;
    },
    generateBundle(_options, bundle) {
      const chunk = Object.values(bundle).find(
        (item) => item.type === 'chunk' && !item.isEntry && item.moduleIds.some((id) => EN_JSON.test(id)),
      );
      if (!chunk) this.error('the English chunk (i18n/en.json) is not in the bundle');
      href = base + chunk.fileName;
    },
    async writeBundle(options) {
      const file = join(options.dir, 'theme-init.js');
      await writeFile(file, (await readFile(file, 'utf8')) + preloadSnippet(href));
    },
  };
}
