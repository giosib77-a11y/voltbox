/**
 * ერთადერთი წერტილი, საიდანაც UI იღებს მონაცემს.
 *
 * კომპონენტები და hooks-ები *მხოლოდ* ამ მოდულს იმპორტირებენ — არასდროს
 * `data/*`-ს და არასდროს კონკრეტულ იმპლემენტაციას.
 *
 * გადართვა: `.env` → VITE_API_MODE=mock | http
 */

/**
 * `virtual:api-impl` იხსნება `vite.config.js`-ში `VITE_API_MODE`-ის მიხედვით:
 *   mock → services/mockApi.js
 *   http → services/httpApi.js
 *
 * ორივე ფაილს იდენტური ხელმოწერები აქვს, ამიტომ UI-სთვის სხვაობა უხილავია.
 * გამოუყენებელი იმპლემენტაცია ბანდლში საერთოდ არ ხვდება.
 */
// eslint-disable-next-line import/no-unresolved
import * as impl from 'virtual:api-impl';

/** @type {typeof import('./mockApi.js')} */
const api = impl;

/* --- კატალოგი ------------------------------------------------------------- */
export const getProducts = api.getProducts;
export const getProductBySlug = api.getProductBySlug;
export const getProductById = api.getProductById;
export const getRelatedProducts = api.getRelatedProducts;
export const getBrands = api.getBrands;
export const getCategories = api.getCategories;
export const getHomeSections = api.getHomeSections;
export const searchProducts = api.searchProducts;

/* --- შეკვეთები ------------------------------------------------------------ */
export const createOrder = api.createOrder;
export const getOrders = api.getOrders;
export const getOrderByNumber = api.getOrderByNumber;

/* --- ავტორიზაცია ---------------------------------------------------------- */
export const login = api.login;
export const register = api.register;
export const logout = api.logout;
export const getProfile = api.getProfile;
export const updateProfile = api.updateProfile;
export const changePassword = api.changePassword;
export const getSessionSync = api.getSessionSync;

/* --- მისამართები ---------------------------------------------------------- */
export const getAddresses = api.getAddresses;
export const saveAddress = api.saveAddress;
export const deleteAddress = api.deleteAddress;

/* --- დიაგნოსტიკა და შეცდომები --------------------------------------------- */
export const apiMode = api.implementation;
export { ApiError, AuthError, NotFoundError, ValidationError } from './errors.js';

export default {
  getProducts,
  getProductBySlug,
  getProductById,
  getRelatedProducts,
  getBrands,
  getCategories,
  getHomeSections,
  searchProducts,
  createOrder,
  getOrders,
  getOrderByNumber,
  login,
  register,
  logout,
  getProfile,
  updateProfile,
  changePassword,
  getSessionSync,
  getAddresses,
  saveAddress,
  deleteAddress,
  apiMode,
};
