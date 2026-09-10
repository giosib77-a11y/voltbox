/**
 * Vitest global setup.
 *
 * What it does: registers jest-dom matchers and clears localStorage plus every
 * mock between tests, so a session written by one test cannot leak into the next.
 * Where it fits: referenced from vite.config.js `test.setupFiles`.
 */

import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';


afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});
