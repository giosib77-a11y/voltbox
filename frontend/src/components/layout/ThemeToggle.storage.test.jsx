/**
 * The switch with storage that throws — Safari's private mode, a locked-down
 * browser, a full quota.
 *
 * A file of its own because the pick storage refuses lives in utils/theme.js's
 * module state for the rest of the page, and vitest isolates files, not tests.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

import ThemeToggle from './ThemeToggle.jsx';
import { mockSystemScheme, removeSystemScheme, runThemeInit } from './themeTesting.js';

beforeEach(() => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new DOMException('denied', 'SecurityError');
  });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('quota', 'QuotaExceededError');
  });
});

afterEach(() => {
  removeSystemScheme();
  document.documentElement.className = '';
});

it('still switches, both ways, for the rest of the session', async () => {
  const user = userEvent.setup();
  mockSystemScheme(false);
  render(<ThemeToggle />);

  await user.click(screen.getByRole('button', { name: 'მუქ თემაზე გადართვა' }));
  expect(screen.getByRole('button', { name: 'ღია თემაზე გადართვა' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'ღია თემაზე გადართვა' }));
  expect(screen.getByRole('button', { name: 'მუქ თემაზე გადართვა' })).toBeInTheDocument();
  expect(Storage.prototype.setItem).toHaveBeenCalled();
});

it('lets the head script fall back to the system setting instead of stopping', () => {
  mockSystemScheme(true);
  expect(runThemeInit()).toBe('theme-dark');
});
