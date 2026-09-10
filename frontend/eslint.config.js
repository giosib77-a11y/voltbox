/**
 * ESLint flat config for the VoltBox frontend.
 *
 * What it does: lints src/ with the recommended JS rules plus the React and
 * react-hooks rules. The hooks rules are the reason this exists — a missing
 * dependency in useEffect is a real bug, not a style preference.
 * Where it fits: `npm run lint`, and the frontend CI job.
 * Notes: generated assets (dist, node_modules) and the SVG generator script are
 * excluded; the script is plain Node and has no React or browser globals.
 */

import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

export default [
  { ignores: ['dist/**', 'node_modules/**', 'coverage/**'] },

  {
    files: ['**/*.{js,jsx}'],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.es2021 },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    settings: { react: { version: '18.3' } },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      // ახალი JSX transform — React-ის იმპორტი აღარ სჭირდება
      'react/react-in-jsx-scope': 'off',
      'react/jsx-uses-react': 'off',
      // PropTypes-ს არ ვიყენებთ; ტიპები JSDoc-შია (src/types.js)
      'react/prop-types': 'off',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // ignoreRestSiblings — `const { passwordHash, ...rest } = user` ველის
      // ჩამოშორების სტანდარტული იდიომაა და არა გამოუყენებელი ცვლადი
      'no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', ignoreRestSiblings: true },
      ],
      // console მხოლოდ აშკარა, დათრგუნული გამონაკლისებით (იხ. ErrorBoundary)
      'no-console': 'error',
    },
  },

  {
    // Node-ის სკრიპტები და კონფიგები — ბრაუზერის გლობალები აქ არ არსებობს
    files: ['scripts/**/*.mjs', '*.config.js', 'vitest.setup.js'],
    languageOptions: { globals: { ...globals.node } },
  },

  {
    files: ['**/*.test.{js,jsx}', 'vitest.setup.js'],
    languageOptions: { globals: { ...globals.node, ...globals.vitest } },
  },
];
