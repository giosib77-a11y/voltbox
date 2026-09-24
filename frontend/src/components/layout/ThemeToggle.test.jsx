/**
 * The storefront's light/dark switch: what it starts on, what it remembers,
 * and that a keyboard can use it.
 *
 * Two halves decide the theme — public/theme-init.js before the first paint,
 * utils/theme.js after — so each rule is checked on both. A page that painted
 * one theme and then flipped to the other is the bug this guards.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import ThemeToggle from './ThemeToggle.jsx';
import { mockSystemScheme, removeSystemScheme, runThemeInit } from './themeTesting.js';
import { STORAGE_KEYS } from '../../constants/index.js';

const TO_DARK = 'მუქ თემაზე გადართვა';
const TO_LIGHT = 'ღია თემაზე გადართვა';

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState({}, '', '/');
});

afterEach(() => {
  removeSystemScheme();
  document.documentElement.className = '';
});

describe('before the shopper picks, the theme follows the system', () => {
  it('starts dark on a dark system and light on a light one', () => {
    mockSystemScheme(true);
    expect(runThemeInit()).toBe('theme-dark');
    const { unmount } = render(<ThemeToggle />);
    expect(screen.getByRole('button', { name: TO_LIGHT })).toBeInTheDocument();
    unmount();

    mockSystemScheme(false);
    expect(runThemeInit()).toBe('theme-light');
    render(<ThemeToggle />);
    expect(screen.getByRole('button', { name: TO_DARK })).toBeInTheDocument();
  });

  it('keeps following when the system setting changes', () => {
    const system = mockSystemScheme(false);
    render(<ThemeToggle />);
    act(() => system.set(true));
    expect(screen.getByRole('button', { name: TO_LIGHT })).toBeInTheDocument();
  });

  it('is light where the browser cannot say', () => {
    removeSystemScheme();
    expect(runThemeInit()).toBe('theme-light');
  });
});

describe("the shopper's pick", () => {
  it('survives a reload, over the system setting', async () => {
    const user = userEvent.setup();
    mockSystemScheme(false);
    const { unmount } = render(<ThemeToggle />);
    await user.click(screen.getByRole('button', { name: TO_DARK }));
    unmount();

    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEYS.theme))).toBe('dark');
    // the reload: the head script first, then a fresh mount
    expect(runThemeInit()).toBe('theme-dark');
    render(<ThemeToggle />);
    expect(screen.getByRole('button', { name: TO_LIGHT })).toBeInTheDocument();
  });

  it('stops the system setting from moving it', async () => {
    const user = userEvent.setup();
    const system = mockSystemScheme(true);
    render(<ThemeToggle />);
    await user.click(screen.getByRole('button', { name: TO_LIGHT }));
    act(() => system.set(false));
    act(() => system.set(true));
    expect(screen.getByRole('button', { name: TO_DARK })).toBeInTheDocument();
  });

  it('ignores a stored value that is not a theme', () => {
    mockSystemScheme(true);
    window.localStorage.setItem(STORAGE_KEYS.theme, JSON.stringify('purple'));
    expect(runThemeInit()).toBe('theme-dark');
    render(<ThemeToggle />);
    expect(screen.getByRole('button', { name: TO_LIGHT })).toBeInTheDocument();
  });
});

it('works from the keyboard: Tab reaches it, Enter and Space switch it', async () => {
  const user = userEvent.setup();
  mockSystemScheme(false);
  render(<ThemeToggle />);

  await user.tab();
  expect(screen.getByRole('button', { name: TO_DARK })).toHaveFocus();
  await user.keyboard('{Enter}');
  expect(screen.getByRole('button', { name: TO_LIGHT })).toHaveFocus();
  await user.keyboard(' ');
  expect(screen.getByRole('button', { name: TO_DARK })).toHaveFocus();
});

describe('the head script', () => {
  it('leaves the admin panel alone', () => {
    mockSystemScheme(true);
    window.localStorage.setItem(STORAGE_KEYS.theme, JSON.stringify('dark'));
    window.history.replaceState({}, '', '/admin/products');
    expect(runThemeInit()).toBe('');
    window.history.replaceState({}, '', '/administrator-tips');
    expect(runThemeInit()).toBe('theme-dark');
  });

  it('reads the key the app writes', () => {
    const source = readFileSync(join(process.cwd(), 'public', 'theme-init.js'), 'utf8');
    expect(source).toContain(`'${STORAGE_KEYS.theme}'`);
  });

  it('runs from <head>, blocking, before the app — and from a file, which the CSP allows', () => {
    const html = readFileSync(join(process.cwd(), 'index.html'), 'utf8');
    const head = html.slice(0, html.indexOf('</head>'));
    const tag = head.match(/<script src="\/theme-init\.js"><\/script>/);
    expect(tag).not.toBeNull();
    expect(head.indexOf(tag[0])).toBeLessThan(html.indexOf('type="module"'));
    // an inline script would be blocked by script-src 'self'; there is none
    expect(html).not.toMatch(/<script(?![^>]*\bsrc=)[^>]*>/);
  });
});
