/*
 * The storefront theme, decided before the first paint.
 *
 * Loaded from <head> as a plain blocking script, so the class is on <html>
 * before the body renders and a dark-theme shopper never sees a white frame.
 * A file and not an inline script: the CSP in render.yaml is
 * `script-src 'self'` with no 'unsafe-inline', which blocks inline code
 * without a word. A same-origin file is what 'self' allows.
 *
 * The same rule as src/utils/theme.js, which takes over once React runs: the
 * shopper's pick from localStorage (`theme:v1`, JSON), else the system
 * setting. Storage that throws counts as no pick. The admin panel is skipped;
 * it has one palette and no switch.
 */
(function () {
  if (/^\/admin(\/|$)/.test(window.location.pathname)) return;
  var theme = null;
  try {
    var stored = JSON.parse(window.localStorage.getItem('theme:v1'));
    if (stored === 'light' || stored === 'dark') theme = stored;
  } catch {
    // private mode or a broken value: fall through to the system setting
  }
  if (!theme) {
    theme =
      window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
  }
  document.documentElement.classList.add('theme-' + theme);
})();
