/** @type {import('tailwindcss').Config} */
export default {
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
      /* ------------------------------------------------------------------
       * Design tokens — VoltBox
       * primary : brand blue (navigation, CTA, links, focus)
       * accent  : volt orange (discounts, highlights, "new")
       * ink     : neutral text / surface scale
       * ---------------------------------------------------------------- */
      colors: {
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
          DEFAULT: '#2440e0',
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
          DEFAULT: '#c74407',
        },
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
        success: {
          50: '#ecfdf5',
          100: '#d1fae5',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
          DEFAULT: '#059669',
        },
        danger: {
          50: '#fef2f2',
          100: '#fee2e2',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          DEFAULT: '#dc2626',
        },
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          500: '#f59e0b',
          600: '#aa5d05',
          DEFAULT: '#aa5d05',
        },
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
  plugins: [],
};
