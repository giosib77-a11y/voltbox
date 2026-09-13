/**
 * Vitest global setup.
 *
 * What it does: fixes the API prefix the tests reason about, registers jest-dom
 * matchers, and clears localStorage plus every mock between tests, so a session
 * written by one test cannot leak into the next.
 * Where it fits: referenced from vite.config.js `test.setupFiles`.
 */

/**
 * The API prefix, for tests only.
 *
 * `httpClient.js` and `session.js` read VITE_API_BASE_URL at module scope, and
 * the tests assert on whole URLs - `/api/v1/auth/refresh`, not `.../refresh`.
 * That value comes from `frontend/.env`, which is gitignored, so it exists on
 * a developer's machine and nowhere else: seven tests passed locally and failed
 * on every clean clone and in CI, where the prefix was the empty string.
 *
 * Set here rather than in the workflow so the suite means the same thing
 * wherever it runs. A value in CI would make CI green while a fresh clone
 * stayed red, which is the shape of the problem, not the fix.
 *
 * What makes the timing work is not the position of this line - ESM hoists the
 * imports below it anyway - but that a setup file finishes before any test file
 * is loaded, and it is the test files that import the modules reading this.
 */
import.meta.env.VITE_API_BASE_URL ||= '/api/v1';

import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';


afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});
