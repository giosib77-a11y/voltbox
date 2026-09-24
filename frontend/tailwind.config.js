import plugin from 'tailwindcss/plugin';

/* ------------------------------------------------------------------------
 * Palette — VoltBox
 *
 * Every colour the app uses is defined here, twice: `light` is the admin
 * panel (and was the whole site until the dark storefront), `dark` is the
 * storefront. Classes do not name hex values; they name a role, and the role
 * resolves through a CSS variable to whichever theme the element sits in.
 *
 * The dark theme applies inside `.theme-dark` (the storefront's Layout root)
 * and to the whole document while one is mounted (`:root:has(.theme-dark)`),
 * which is what reaches the body background and the Modal and Toast portals.
 * The admin never mounts `.theme-dark`, so it resolves every variable to
 * `light` — the same hex values it used before this palette existed.
 *
 * A step keeps its job in both themes; only its value moves:
 *   ink-50  page background       ink-100 raised fill, hover
 *   surface cards, panels, inputs ink-200 dividers (decorative)
 *   ink-300 control borders       ink-400 icons, separators, disabled
 *   ink-500 muted text            ink-600…900 text, strongest at 900
 *   primary-50…200 tints   400/500 borders, focus   600 solid fill
 *   primary-700…900 text on a surface or a tint
 * `primary-hover`/`-press` exist because the solid button's states used
 * primary-700/800, which are text colours in the dark theme. `danger-fg` is
 * there for the same reason: danger-600 is both the danger button's fill and
 * the error text, and no red is readable on white text and on near-black too.
 *
 * Contrast ratios for the dark pairs are in the commit that introduced this.
 * ---------------------------------------------------------------------- */
const palette = {
  light: {
    surface: '#ffffff',
    // behind product photos; the same light tile in both themes
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
  },
  dark: {
    surface: '#12151c',
    media: '#eef0f4',
    'media-shade': '#dde1e9',
    scrim: '#000000',
    ink: {
      50: '#0a0c10',
      100: '#1a1e27',
      200: '#262b36',
      300: '#646d80',
      400: '#737c90',
      500: '#959db0',
      600: '#aab1c1',
      700: '#c0c6d2',
      800: '#d6dbe3',
      900: '#eceef3',
      950: '#f7f8fa',
    },
    primary: {
      50: '#141a36',
      100: '#1a2250',
      200: '#222e6e',
      300: '#2e3c8f',
      400: '#5b78ff',
      500: '#7690ff',
      600: '#3a5bf5',
      700: '#9db3ff',
      800: '#bfceff',
      900: '#dde6ff',
      950: '#eef3ff',
      hover: '#2f4de6',
      press: '#2842cc',
    },
    accent: {
      50: '#2a180b',
      100: '#3a200c',
      200: '#5c3413',
      300: '#8a4a17',
      400: '#ffa24a',
      500: '#ff8a2a',
      600: '#c74407',
      700: '#a8390a',
      800: '#8f320c',
      900: '#66250c',
    },
    success: {
      50: '#0d2419',
      100: '#113020',
      500: '#34d399',
      600: '#34d399',
      700: '#6ee7b7',
    },
    danger: {
      50: '#2a1114',
      100: '#3a1519',
      500: '#f87171',
      600: '#dc2626',
      700: '#b91c1c',
      fg: '#fca5a5',
    },
    warning: {
      50: '#2a1f08',
      100: '#3a2a0a',
      500: '#f59e0b',
      600: '#fbbf24',
    },
  },
};

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

const themed = colorsFrom(palette.light);

/** @type {import('tailwindcss').Config} */
export default {
  // `dark:` = inside the storefront. Only for what a token cannot say (a blend
  // mode); colours go through the palette.
  darkMode: ['variant', ['&:is(.theme-dark *)', ':root:has(.theme-dark) &']],
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
    plugin(({ addBase }) => {
      addBase({
        ':root': cssVariables(palette.light),
        '.theme-dark, :root:has(.theme-dark)': {
          ...cssVariables(palette.dark),
          'color-scheme': 'dark',
        },
      });
    }),
  ],
};
