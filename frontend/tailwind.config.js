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
 *   light  the storefront's light theme: warm paper, DESIGN.md §2.2.
 *   dark   the storefront's dark theme: near-black and gold, DESIGN.md §2.2.
 *
 * Radius, shadow, icon stroke and button weight are theme tokens too, by the
 * same mechanism (`themeTokens` below -> `--radius-*`, `--shadow-*`, ...): the
 * admin's values are what the whole site used before the redesign.
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
 *   on-primary text and icons on a primary-600 fill (admin: white)
 *   footer  the footer's background (admin: white, as the card it was)
 *   glow    the centre of the hero ornament's radial glow
 *   outline the 1px contour of a button that carries its own label or icon
 *           (admin: ink-300, the old outline button's border)
 *   scrim   modal backdrop       media / media-shade  the product photo tile
 * `primary-hover`/`-press`, `danger-fg` and `accent-fg` exist because one
 * step used to do two jobs: fill behind white text, and text on the page.
 * No colour passes 4.5:1 against white and against a dark page at once.
 * `on-primary` exists because a dark theme's primary fill is gold, which
 * takes dark text.
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
  // text and icons on a primary-600 fill
  'on-primary': '#ffffff',
  // the footer's background; the admin has none, a card is white
  footer: '#ffffff',
  // centre of the hero ornament's glow; the admin does not draw it
  glow: '#eef3ff',
  // contour of a button that carries its own label or icon
  outline: '#c2c9d6',
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

// Warm paper. success / danger / warning are the admin's, bar the two steps
// the new canvas pushed under AA (accent-fg, danger-fg).
const light = {
  ...admin,
  surface: '#FFFFFF',
  media: '#F5F1E9',
  'media-shade': '#EDE7DB',
  scrim: '#1C1B19',
  'on-primary': '#F7F4EE',
  footer: '#EFEAE0',
  glow: '#FBF6EC',
  outline: '#D6CDBC',
  ink: {
    50: '#F7F4EE',
    100: '#EFEAE0',
    200: '#E6E0D4',
    // control borders and icons: 3:1 is the floor
    300: '#8C8474',
    400: '#8C8474',
    500: '#6D6860',
    600: '#58534C',
    700: '#46423C',
    800: '#302D29',
    900: '#1C1B19',
    950: '#0E0E0F',
  },
  primary: {
    50: '#F6F0E4',
    100: '#F1E9D8',
    200: '#DCCBA6',
    300: '#C9C2B3',
    400: '#BDA06C',
    500: '#A18046',
    600: '#1C1B19',
    700: '#826330',
    800: '#6B5226',
    900: '#4F3B17',
    950: '#2E2310',
    hover: '#3A3733',
    press: '#0E0E0F',
  },
  accent: {
    ...admin.accent,
    // rating stars: 2.09:1 on white before
    400: '#d26a08',
    // discount text: 4.49:1 on the new canvas before
    fg: '#C24307',
  },
  danger: {
    ...admin.danger,
    // error text: 4.41:1 on danger-50 before
    fg: '#c81e1e',
  },
};

const dark = {
  surface: '#131315',
  media: '#F5F1E9',
  'media-shade': '#EDE7DB',
  scrim: '#000000',
  'on-primary': '#0E0E0F',
  footer: '#0A0A0B',
  glow: '#2B2720',
  outline: '#3A3A40',
  ink: {
    50: '#0E0E0F',
    100: '#1D1D20',
    200: '#26262A',
    300: '#6A6A70',
    400: '#6A6A70',
    500: '#A19B91',
    600: '#B8B2A8',
    700: '#CDC8BF',
    800: '#DFDAD2',
    900: '#EDE9E3',
    950: '#F7F4EE',
  },
  primary: {
    50: '#1A1917',
    100: '#2B2720',
    200: '#3A3326',
    300: '#5C5240',
    400: '#D8BD84',
    500: '#C9A96E',
    600: '#C9A96E',
    700: '#C9A96E',
    800: '#D8BD84',
    900: '#E8D6B0',
    950: '#F3EBD8',
    hover: '#D8BD84',
    press: '#B49456',
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

/* ------------------------------------------------------------------------
 * Theme tokens that are not colours (DESIGN.md §5). Same three themes, same
 * variables mechanism; the admin column is what the whole site used before
 * the redesign and src/utils/palette.test.js pins it to those literals.
 *
 * "No shadow" is `0 0 #0000`, not `none`: Tailwind lists the ring shadows and
 * this one in a single `box-shadow`, and `none` inside a list makes the whole
 * declaration invalid — a focus ring on a card would vanish.
 * ---------------------------------------------------------------------- */
const NO_SHADOW = '0 0 #0000';

const adminTokens = {
  'radius-control': '0.625rem',
  'radius-card': '0.875rem',
  'shadow-card': '0 1px 2px 0 rgb(18 21 29 / 0.04), 0 1px 3px 0 rgb(18 21 29 / 0.06)',
  'shadow-card-hover': '0 10px 24px -6px rgb(18 21 29 / 0.14), 0 2px 6px -2px rgb(18 21 29 / 0.08)',
  'shadow-popover': '0 12px 32px -8px rgb(18 21 29 / 0.22), 0 4px 10px -4px rgb(18 21 29 / 0.10)',
  'shadow-header': '0 1px 0 0 rgb(18 21 29 / 0.06)',
  // a dark page has no room for a drop shadow; a hovered card glows instead
  'shadow-glow': '0 0 0 1px rgb(var(--c-primary-400) / 0.25), 0 14px 36px -14px rgb(var(--c-primary-600) / 0.6)',
  'shadow-btn': '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  // corner of the global :focus-visible ring on an element with no radius of its own
  'focus-radius': '0.125rem',
  'icon-stroke': '2',
  'icon-stroke-fine': '2',
  'btn-weight': '600',
  'btn-tracking': '0',
};

const hoverGlow = (ring, drop) => `0 0 0 1px rgb(var(--c-primary-500) / ${ring}), ${drop}`;

const lightTokens = {
  'radius-control': '2px',
  'radius-card': '0px',
  'shadow-card': NO_SHADOW,
  'shadow-card-hover': hoverGlow('0.45', '0 14px 32px -18px rgb(60 48 30 / 0.25)'),
  'shadow-popover': '0 18px 40px -14px rgb(60 48 30 / 0.28), 0 2px 8px -2px rgb(60 48 30 / 0.12)',
  'shadow-header': NO_SHADOW,
  'shadow-glow': hoverGlow('0.45', '0 14px 32px -18px rgb(60 48 30 / 0.25)'),
  'shadow-btn': NO_SHADOW,
  'focus-radius': '0px',
  'icon-stroke': '1.4',
  'icon-stroke-fine': '1.1',
  'btn-weight': '500',
  'btn-tracking': '0.04em',
};

const darkTokens = {
  ...lightTokens,
  'shadow-card-hover': hoverGlow('0.4', '0 18px 40px -18px rgb(0 0 0 / 0.8)'),
  'shadow-popover': '0 20px 48px -12px rgb(0 0 0 / 0.75), 0 0 0 1px rgb(var(--c-ink-200))',
  'shadow-glow': hoverGlow('0.4', '0 18px 40px -18px rgb(0 0 0 / 0.8)'),
};

export const themeTokens = { admin: adminTokens, light: lightTokens, dark: darkTokens };

/** { 'radius-card': '0px' } → { '--radius-card': '0px' } */
function tokenVariables(tokens) {
  return Object.fromEntries(Object.entries(tokens).map(([name, value]) => [`--${name}`, value]));
}

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
        // headings, card names, benefit and footer titles (Georgian and Latin)
        serif: ['"Noto Serif Georgian"', 'Georgia', '"Times New Roman"', 'serif'],
        // wordmark, hero display, prices and brand label. Cormorant has no
        // Georgian glyphs: Georgian text in it falls through to Noto Serif.
        display: ['"Cormorant Garamond"', '"Noto Serif Georgian"', 'Georgia', '"Times New Roman"', 'serif'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      borderRadius: {
        card: 'var(--radius-card)',
        control: 'var(--radius-control)',
        pill: '9999px',
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        'card-hover': 'var(--shadow-card-hover)',
        popover: 'var(--shadow-popover)',
        header: 'var(--shadow-header)',
        glow: 'var(--shadow-glow)',
        btn: 'var(--shadow-btn)',
      },
      maxWidth: {
        // 1320px of content + 2 x 24px gutters (border-box), DESIGN.md §4
        container: '1368px',
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
      const variables = (name) => ({ ...cssVariables(palette[name]), ...tokenVariables(themeTokens[name]) });
      addBase({ ':root': variables('admin') });
      addBase({ ':root.theme-light': variables('light') });
      addBase({ ':root.theme-dark': { ...variables('dark'), 'color-scheme': 'dark' } });
      addBase({ '[data-admin]': { ...variables('admin'), 'color-scheme': 'light' } });
      addBase({
        ':root:has([data-admin])': { ...variables('admin'), 'color-scheme': 'light' },
      });
      // `storefront:` = inside the shop's Layout, in either theme. For what a
      // token cannot say: the product photo's blend into its tile.
      addVariant('storefront', ':is([data-storefront] &)');
    }),
  ],
};
