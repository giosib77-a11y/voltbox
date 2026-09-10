/**
 * Admin REST client.
 *
 * What it does: every call the admin panel makes, on top of the shared HTTP
 * client, so the admin inherits the bearer header and the 401 refresh retry.
 * Where it fits: imported only by pages under src/admin/, which are lazy-loaded
 * and therefore live in their own chunk.
 * Notes: the admin is http-only by design. mockApi deliberately does not
 * implement these endpoints - faking writes against in-memory data would prove
 * nothing about the real inventory and audit rules. `isAdminAvailable()` lets
 * the routes render a notice instead in mock builds.
 */

import { request } from '../services/httpClient.js';

/** True when the build talks to a real backend. */
export function isAdminAvailable() {
  return import.meta.env?.VITE_API_MODE === 'http';
}

// GET /admin/me
export async function getAdminProfile() {
  return request('/admin/me');
}
