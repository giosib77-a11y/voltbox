/**
 * Tests for crash reporting.
 *
 * The point of this module is that a blank screen in a customer's browser
 * leaves a record somewhere. The point of these tests is the other half: that
 * reporting a crash never makes the crash worse.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { __resetErrorReportingForTests, reportError } from './reportError.js';

const ORIGINAL_MODE = import.meta.env.VITE_API_MODE;

beforeEach(() => {
  __resetErrorReportingForTests();
  import.meta.env.VITE_API_MODE = 'http';
  global.fetch = vi.fn(async () => ({ ok: true, status: 204 }));
});

afterEach(() => {
  import.meta.env.VITE_API_MODE = ORIGINAL_MODE;
});

describe('reporting a crash', () => {
  it('posts the message and where it happened', async () => {
    await reportError(new Error('Cannot read properties of undefined'), {
      componentStack: '\n    at ProductCard',
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toMatch(/\/client-errors$/);
    const body = JSON.parse(options.body);
    expect(body.message).toBe('Cannot read properties of undefined');
    expect(body.stack).toContain('ProductCard');
  });

  it('survives the reload the user is about to do', () => {
    // Without keepalive the request is cancelled with the page, and the crash
    // goes unrecorded after all.
    reportError(new Error('boom'));

    expect(global.fetch.mock.calls[0][1].keepalive).toBe(true);
  });

  it('reports once, however many times the render loop tries', async () => {
    await reportError(new Error('boom'));
    await reportError(new Error('boom'));
    await reportError(new Error('boom'));

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('stays quiet when there is no backend to tell', async () => {
    import.meta.env.VITE_API_MODE = 'mock';

    await reportError(new Error('boom'));

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('swallows its own failure', async () => {
    // The application has already broken. An unhandled rejection from the
    // thing reporting that is not an improvement.
    global.fetch = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });

    await expect(reportError(new Error('boom'))).resolves.toBe(false);
  });

  it('keeps the message inside the caps the API enforces', async () => {
    await reportError(new Error('x'.repeat(5000)));

    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.message.length).toBe(300);
  });

  it('says something even for a thrown value that is not an Error', async () => {
    await reportError('a bare string');

    expect(JSON.parse(global.fetch.mock.calls[0][1].body).message).toBe('a bare string');
  });
});
