/**
 * Admin REST client.
 *
 * What it does: every call the admin panel makes, on top of the shared HTTP
 * client, so the admin inherits the bearer header and the 401 refresh retry.
 * Where it fits: imported only by pages under src/admin/, which are lazy-loaded
 * and therefore live in their own chunk.
 * Notes: the admin is http-only by design. mockApi deliberately does not
 * implement these endpoints - faking writes against in-memory data would prove
 * nothing about the real inventory and audit rules.
 */

import { request } from '../services/httpClient.js';

/** True when the build talks to a real backend. */
export function isAdminAvailable() {
  return import.meta.env?.VITE_API_MODE === 'http';
}

/* ------------------------------------------------------------------ me --- */

// GET /admin/me
export async function getAdminProfile() {
  return request('/admin/me');
}

/* ------------------------------------------------------------ products --- */

// GET /admin/products?page=&limit=&sort=&q=&categoryId=&...
export async function listProducts(params = {}) {
  return request('/admin/products', { params });
}

// GET /admin/products/:id
export async function getProduct(id) {
  return request(`/admin/products/${encodeURIComponent(id)}`);
}

// POST /admin/products
export async function createProduct(payload) {
  return request('/admin/products', { method: 'POST', body: payload });
}

// PATCH /admin/products/:id
export async function updateProduct(id, patch) {
  return request(`/admin/products/${encodeURIComponent(id)}`, { method: 'PATCH', body: patch });
}

// POST /admin/products/:id/archive
export async function archiveProduct(id) {
  return request(`/admin/products/${encodeURIComponent(id)}/archive`, { method: 'POST' });
}

// POST /admin/products/:id/unarchive
export async function unarchiveProduct(id) {
  return request(`/admin/products/${encodeURIComponent(id)}/unarchive`, { method: 'POST' });
}

// POST /admin/products/:id/duplicate
export async function duplicateProduct(id) {
  return request(`/admin/products/${encodeURIComponent(id)}/duplicate`, { method: 'POST' });
}

/* -------------------------------------------------------------- images --- */

// POST /admin/products/:id/images (multipart)
export async function uploadProductImage(productId, file) {
  const form = new FormData();
  form.append('file', file);
  // No Content-Type header: the browser sets it with the multipart boundary.
  return request(`/admin/products/${encodeURIComponent(productId)}/images`, {
    method: 'POST',
    body: form,
  });
}

// PUT /admin/products/:id/images/order
export async function reorderProductImages(productId, imageIds) {
  return request(`/admin/products/${encodeURIComponent(productId)}/images/order`, {
    method: 'PUT',
    body: { imageIds },
  });
}

// POST /admin/products/:id/images/:imageId/primary
export async function setPrimaryImage(productId, imageId) {
  return request(
    `/admin/products/${encodeURIComponent(productId)}/images/${encodeURIComponent(imageId)}/primary`,
    { method: 'POST' },
  );
}

// DELETE /admin/products/:id/images/:imageId
export async function deleteProductImage(productId, imageId) {
  return request(
    `/admin/products/${encodeURIComponent(productId)}/images/${encodeURIComponent(imageId)}`,
    { method: 'DELETE' },
  );
}

/* ---------------------------------------------------------- categories --- */

// GET /admin/categories
export async function listCategories() {
  return request('/admin/categories');
}

// POST /admin/categories
export async function createCategory(payload) {
  return request('/admin/categories', { method: 'POST', body: payload });
}

// PATCH /admin/categories/:id
export async function updateCategory(id, patch) {
  return request(`/admin/categories/${encodeURIComponent(id)}`, { method: 'PATCH', body: patch });
}

// DELETE /admin/categories/:id
export async function deleteCategory(id) {
  return request(`/admin/categories/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

/* -------------------------------------------------------------- brands --- */

// GET /admin/brands
export async function listBrands() {
  return request('/admin/brands');
}

// POST /admin/brands
export async function createBrand(payload) {
  return request('/admin/brands', { method: 'POST', body: payload });
}

// PATCH /admin/brands/:id
export async function updateBrand(id, patch) {
  return request(`/admin/brands/${encodeURIComponent(id)}`, { method: 'PATCH', body: patch });
}

// DELETE /admin/brands/:id
export async function deleteBrand(id) {
  return request(`/admin/brands/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

/* -------------------------------------------------------------- orders --- */

// GET /admin/orders?page=&limit=&q=&status=&dateFrom=&dateTo=
export async function listOrders(params = {}) {
  return request('/admin/orders', { params });
}

// GET /admin/orders/:id
export async function getOrder(id) {
  return request(`/admin/orders/${encodeURIComponent(id)}`);
}

// POST /admin/orders/:id/status
export async function changeOrderStatus(id, to, note) {
  return request(`/admin/orders/${encodeURIComponent(id)}/status`, {
    method: 'POST',
    body: { to, note: note || null },
  });
}

/* ----------------------------------------------------------- inventory --- */

// GET /admin/inventory?page=&limit=&q=&only=
export async function listInventory(params = {}) {
  return request('/admin/inventory', { params });
}

// POST /admin/inventory/:productId/adjust
export async function adjustStock(productId, payload) {
  return request(`/admin/inventory/${encodeURIComponent(productId)}/adjust`, {
    method: 'POST',
    body: payload,
  });
}

// GET /admin/inventory/:productId/movements
export async function listMovements(productId, params = {}) {
  return request(`/admin/inventory/${encodeURIComponent(productId)}/movements`, { params });
}

/* ----------------------------------------------------------- dashboard --- */

// GET /admin/dashboard
export async function getDashboard() {
  return request('/admin/dashboard');
}
