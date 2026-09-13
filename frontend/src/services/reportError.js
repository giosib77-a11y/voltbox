/**
 * Tell the server that this browser crashed.
 *
 * What it does: posts one short report to /client-errors, which writes it to
 * the same log the API writes everything else to.
 * Where it fits: called by ErrorBoundary, and by nothing else.
 *
 * Why it exists: a server error has had a traceback and a request id since
 * section 13. A crash here had neither - the screen went blank and no record
 * of it existed anywhere, so the shop learned about it when somebody phoned,
 * or never.
 *
 * Notes: deliberately not the shared httpClient. That one refreshes tokens,
 * retries, parses envelopes and throws typed errors - none of which belongs on
 * a path taken by an application that has already broken. `keepalive` lets the
 * report survive the reload the user is about to do.
 */

const ENDPOINT = '/client-errors';
const MAX_MESSAGE = 300;
const MAX_STACK = 2000;

/** One report per page load. A render loop must not become a request loop. */
let alreadyReported = false;

export function __resetErrorReportingForTests() {
  alreadyReported = false;
}

function base() {
  return import.meta.env?.VITE_API_BASE_URL || '/api/v1';
}

export function reportError(error, info) {
  if (alreadyReported) return Promise.resolve(false);
  alreadyReported = true;

  // Only where there is a real backend. In mock mode there is nothing
  // listening, and a failed report in the console is noise about noise.
  if (import.meta.env?.VITE_API_MODE !== 'http') return Promise.resolve(false);

  const body = JSON.stringify({
    message: String(error?.message || error || 'unknown error').slice(0, MAX_MESSAGE),
    path: `${window.location?.pathname || ''}${window.location?.search || ''}`.slice(0, 300),
    stack: String(info?.componentStack || error?.stack || '').slice(0, MAX_STACK),
  });

  return fetch(`${base()}${ENDPOINT}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    // The user is one click away from reloading; without this the request is
    // cancelled with the page and the crash goes unrecorded after all.
    keepalive: true,
  })
    .then(() => true)
    .catch(() => false); // Reporting a failure to report helps nobody.
}

export default reportError;
