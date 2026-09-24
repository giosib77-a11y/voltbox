import plugin from 'tailwindcss/plugin';

/* ------------------------------------------------------------------------
 * Palette — VoltBox
 *
 * Every colour the app uses is defined here, once per theme. Classes do not
 * name hex values; they name a role, and the role resolves through a CSS
 * variable to the theme the page is in:
 *
 *   admin  the admin panel, frozen. It is what the whole site looked like
 *          before the storefront had themes, and the panel must not move.
 *   light  the storefront's light theme: `admin` with the five steps that
 *          missed WCAG AA on it corrected (see the overrides below).
 *   dark   the storefront's dark theme.
 *
 * `:root` carries `admin`, so anything outside the storefront is unchanged.
 * The storefront's theme is a class on <html>, `theme-light` or `theme-dark`,
 * set before first paint by public/theme-init.js and kept in step by
 * src/utils/theme.js. The admin tree carries `data-admin`, which resets the
 * variables to `admin` — for the panel itself, and for the whole document
 * while it is mounted, because a shopper can walk from the shop into the
 * panel without a reload and the class on <html> stays behind.
 *
 * A step keeps its job in every theme; only its value moves:
 *   ink-50  page background       ink-100 raised fill, hover
 *   surface cards, panels, inputs ink-200 dividers (decorative)
 *   ink-300 control borders       ink-400 icons, separators, disabled
 *   ink-500 muted text            ink-600…900 text, strongest at 900
 *   primary-50…200 tints   400/500 borders, focus   600 solid fill
 *   primary-700…900 text on a surface or a tint
 * `primary-hover`/`-press`, `danger-fg` and `accent-fg` exist because one
 * step used to do two jobs: fill behind white text, and text on the page.
 * No colour passes 4.5:1 against white and against a dark page at once.
 *
 * src/utils/palette.test.js holds every text/background pair to WCAG AA in
 * both storefront themes; change a value here and it re-measures.
 * ---------------------------------------------------------------------- */
const admin = {
  surface: '#ffffff',
  // behind product photos; the same light tile in every theme
  media: '#eef0f4',
  'media-shade': '#dde1e9',
  // modal backdrop
  scrim: '#12151d',
  ink: {
    50: '#f7f8fa',
    100: '#eef0f4',
    200: '#dde1e9',
    300: '#c2c9d6',
    400: '#97a1b5',
    500: '#657086',
    600: '#56617a',
    700: '#454e63',
    800: '#333a4a',
    900: '#1e2330',
    950: '#12151d',
  },
  primary: {
    50: '#eef3ff',
    100: '#dbe5ff',
    200: '#bfd0ff',
    300: '#94b0ff',
    400: '#6285ff',
    500: '#3a5bf5',
    600: '#2440e0',
    700: '#1e33bd',
    800: '#1d2f99',
    900: '#1e2e79',
    950: '#141c47',
    hover: '#1e33bd',
    press: '#1d2f99',
  },
  accent: {
    50: '#fff8ed',
    100: '#ffefd4',
    200: '#ffdba8',
    300: '#ffc071',
    400: '#ff9c38',
    500: '#ff7f11',
    600: '#c74407',
    700: '#9e360e',
    800: '#7f2e0f',
    900: '#66250c',
    fg: '#c74407',
  },
  success: {
    50: '#ecfdf5',
    100: '#d1fae5',
    500: '#10b981',
    600: '#059669',
    700: '#047857',
  },
  danger: {
    50: '#fef2f2',
    100: '#fee2e2',
    500: '#ef4444',
    600: '#dc2626',
    700: '#b91c1c',
    fg: '#dc2626',
  },
  warning: {
    50: '#fffbeb',
    100: '#fef3c7',
    500: '#f59e0b',
    600: '#aa5d05',
  },
};

const light = {
  ...admin,
  ink: {
    ...admin.ink,
    // control borders: 1.46–1.66:1 before, 3:1 is the floor
    300: '#7b8599',
    // icons and separators: 2.28–2.60:1 before
    400: '#6f798e',
    // muted text: 4.37:1 on ink-100 before
    500: '#5f6a80',
  },
  accent: {
    ...admin.accent,
    // rating stars: 2.09:1 on white before
    400: '#d26a08',
  },
  danger: {
    ...admin.danger,
    // error text: 4.41:1 on danger-50 before
    fg: '#c81e1e',
  },
};

const dark = {
  surface: '#1f242e',
  media: '#eef0f4',
  'media-shade': '#dde1e9',
  scrim: '#05070a',
  ink: {
    50: '#171b23',
    100: '#283040',
    200: '#353d4d',
    300: '#747d93',
    400: '#7f889d',
    500: '#a3abbd',
    600: '#b8bfcd',
    700: '#cad0da',
    800: '#dde1e8',
    900: '#f0f2f6',
    950: '#f8f9fb',
  },
  primary: {
    50: '#1f2749',
    100: '#252f62',
    200: '#2e3a80',
    300: '#3a4899',
    400: '#6583ff',
    500: '#7f98ff',
    600: '#4466f7',
    700: '#a7bbff',
    800: '#c4d2ff',
    900: '#e0e8ff',
    950: '#eef3ff',
    hover: '#3558ea',
    press: '#2d4ed8',
  },
  accent: {
    50: '#33220f',
    100: '#422a10',
    200: '#5c3a17',
    300: '#8a4a17',
    400: '#ffa24a',
    500: '#ff8a2a',
    600: '#c74407',
    700: '#a8390a',
    800: '#8f320c',
    900: '#66250c',
    fg: '#ffa24a',
  },
  success: {
    50: '#14302a',
    100: '#173a31',
    500: '#34d399',
    600: '#34d399',
    700: '#6ee7b7',
  },
  danger: {
    50: '#331a1f',
    100: '#421d23',
    500: '#f87171',
    600: '#dc2626',
    700: '#b91c1c',
    fg: '#fca5a5',
  },
  warning: {
    50: '#33290f',
    100: '#423411',
    500: '#f59e0b',
    600: '#fbbf24',
  },
};

export const palette = { admin, light, dark };

/** `#rrggbb` → `r g b`, the form `rgb(var(--x) / <alpha-value>)` needs. */
function channels(hex) {
  const n = parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
}

/** { ink: { 50: '#..' } } → { '--c-ink-50': 'r g b' } */
function cssVariables(theme) {
  const out = {};
  for (const [name, value] of Object.entries(theme)) {
    if (typeof value === 'string') {
      out[`--c-${name}`] = channels(value);
    } else {
      for (const [step, hex] of Object.entries(value)) out[`--c-${name}-${step}`] = channels(hex);
    }
  }
  return out;
}

/** The tailwind colour map: same shape as the palette, values are variables. */
function colorsFrom(theme) {
  const ref = (key) => `rgb(var(--c-${key}) / <alpha-value>)`;
  const out = {};
  for (const [name, value] of Object.entries(theme)) {
    if (typeof value === 'string') {
      out[name] = ref(name);
    } else {
      out[name] = Object.fromEntries(Object.keys(value).map((step) => [step, ref(`${name}-${step}`)]));
    }
  }
  return out;
}

const themed = colorsFrom(palette.admin);

/** @type {import('tailwindcss').Config} */
export default {
  // No `darkMode`: a theme is the palette, never a `dark:` class on one
  // element. src/utils/palette.test.js fails on any `dark:` in the source.
  // `relative: true` — glob-ები ამ ფაილის მიმართ იხსნება და არა
  // `process.cwd()`-ის მიმართ. ამის გარეშე repo-ს ძირიდან გაშვებული ბილდი
  // ვერცერთ კლასს ვერ იპოვის და CSS თითქმის ცარიელი გამოვა — warning-ით,
  // მაგრამ შეცდომის გარეშე.
  content: {
    relative: true,
    files: ['./index.html', './src/**/*.{js,jsx}'],
  },
  theme: {
    extend: {
      // The palette above, by role. `canvas`, `surface`, `line`, `fg` and
      // `fg-muted` are names for ink steps and new code should prefer them;
      // `primary` is the one accent colour, `accent` (orange) marks prices
      // and discounts only.
      colors: {
        ...themed,
        primary: { ...themed.primary, DEFAULT: themed.primary[600] },
        accent: { ...themed.accent, DEFAULT: themed.accent[600] },
        success: { ...themed.success, DEFAULT: themed.success[600] },
        danger: { ...themed.danger, DEFAULT: themed.danger[600] },
        warning: { ...themed.warning, DEFAULT: themed.warning[600] },
        canvas: themed.ink[50],
        line: { DEFAULT: themed.ink[200], strong: themed.ink[300] },
        fg: { DEFAULT: themed.ink[900], muted: themed.ink[500] },
      },
      fontFamily: {
        sans: [
          '"Noto Sans Georgian"',
          'Inter',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      borderRadius: {
        card: '0.875rem',
        control: '0.625rem',
        pill: '9999px',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(18 21 29 / 0.04), 0 1px 3px 0 rgb(18 21 29 / 0.06)',
        'card-hover': '0 10px 24px -6px rgb(18 21 29 / 0.14), 0 2px 6px -2px rgb(18 21 29 / 0.08)',
        popover: '0 12px 32px -8px rgb(18 21 29 / 0.22), 0 4px 10px -4px rgb(18 21 29 / 0.10)',
        header: '0 1px 0 0 rgb(18 21 29 / 0.06)',
        // a dark page has no room for a drop shadow; a hovered card glows instead
        glow: '0 0 0 1px rgb(var(--c-primary-400) / 0.25), 0 14px 36px -14px rgb(var(--c-primary-600) / 0.6)',
      },
      maxWidth: {
        container: '1400px',
      },
      zIndex: {
        header: '40',
        drawer: '50',
        modal: '60',
        toast: '70',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          from: { transform: 'translateX(100%)' },
          to: { transform: 'translateX(0)' },
        },
        'slide-in-left': {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(0)' },
        },
        'sheet-up': {
          from: { transform: 'translateY(100%)' },
          to: { transform: 'translateY(0)' },
        },
        'badge-pop': {
          '0%': { transform: 'scale(1)' },
          '35%': { transform: 'scale(1.45)' },
          '70%': { transform: 'scale(0.92)' },
          '100%': { transform: 'scale(1)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 180ms ease-out both',
        'slide-up': 'slide-up 220ms cubic-bezier(0.22, 1, 0.36, 1) both',
        'slide-in-right': 'slide-in-right 260ms cubic-bezier(0.22, 1, 0.36, 1) both',
        'slide-in-left': 'slide-in-left 260ms cubic-bezier(0.22, 1, 0.36, 1) both',
        'sheet-up': 'sheet-up 260ms cubic-bezier(0.22, 1, 0.36, 1) both',
        'badge-pop': 'badge-pop 420ms cubic-bezier(0.34, 1.56, 0.64, 1)',
        shimmer: 'shimmer 1.6s infinite',
      },
    },
  },
  plugins: [
    plugin(({ addBase, addVariant }) => {
      // Separate rules, in this order: the later ones win at equal
      // specificity, and a browser without `:has` drops only its own rule.
      addBase({ ':root': cssVariables(palette.admin) });
      addBase({ ':root.theme-light': cssVariables(palette.light) });
      addBase({ ':root.theme-dark': { ...cssVariables(palette.dark), 'color-scheme': 'dark' } });
      addBase({ '[data-admin]': { ...cssVariables(palette.admin), 'color-scheme': 'light' } });
      addBase({
        ':root:has([data-admin])': { ...cssVariables(palette.admin), 'color-scheme': 'light' },
      });
      // `storefront:` = inside the shop's Layout, in either theme. For what a
      // token cannot say: the product photo's blend into its tile.
      addVariant('storefront', ':is([data-storefront] &)');
    }),
  ],
};
