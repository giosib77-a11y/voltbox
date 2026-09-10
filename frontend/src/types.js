/**
 * მონაცემთა კონტრაქტი Frontend-სა და (მომავალ) Backend-ს შორის.
 * ეს ფაილი მხოლოდ JSDoc ტიპებს შეიცავს — runtime კოდი აქ არ არის.
 * გამოიყენე `@type {import('../types.js').Product}` ავტოკომპლიტისთვის.
 */

/**
 * @typedef {'phones'|'cables'|'powerbanks'|'chargers'|'headphones'|'accessories'} CategoryId
 */

/**
 * @typedef {Object} Product
 * @property {string} id                       უნიკალური იდენტიფიკატორი, მაგ. "ph-001"
 * @property {string} slug                     URL-ისთვის, მაგ. "samsung-galaxy-s24-256gb"
 * @property {string} name
 * @property {string} brand
 * @property {CategoryId} category
 * @property {string} shortDescription
 * @property {string} description
 * @property {number} price                    GEL
 * @property {number|null} oldPrice            GEL ან null
 * @property {number} rating                   0–5
 * @property {number} reviewsCount
 * @property {number} stock                    0 = მარაგში არ არის
 * @property {boolean} isNew
 * @property {boolean} isFeatured
 * @property {string[]} images                 მინიმუმ 3
 * @property {Record<string, string|number|boolean>} specs
 * @property {string[]} tags
 * @property {string} createdAt                ISO 8601
 */

/**
 * წარმოებული ველები — ითვლება data layer-ში, mock-ში ხელით არასდროს იწერება.
 * @typedef {Product & {
 *   brandCountry: string|null,
 *   discountPercent: number,
 *   hasDiscount: boolean,
 *   inStock: boolean,
 *   isLowStock: boolean
 * }} DecoratedProduct
 */

/**
 * @typedef {Object} CategoryFilter
 * @property {string} key                      "brand" | "specs.ram" | ...
 * @property {string} label
 * @property {'checkbox'|'toggle'|'swatch'} type
 * @property {*} [match]                       toggle-ისთვის: „ჩართულის“ მნიშვნელობა
 * @property {string} [param]                  URL პარამეტრის სახელი (default: key-ის ბოლო სეგმენტი)
 */

/**
 * @typedef {Object} Category
 * @property {CategoryId} id
 * @property {string} name
 * @property {string} slug
 * @property {string} icon                     lucide-react-ის აიქონის სახელი
 * @property {string} description
 * @property {CategoryFilter[]} filters
 */

/**
 * @typedef {Object} CartLine
 * @property {string} productId
 * @property {number} qty
 * @property {{ name:string, slug:string, image:string, price:number, oldPrice:number|null, stock:number }} snapshot
 */

/**
 * @typedef {Object} ProductListResult
 * @property {DecoratedProduct[]} items
 * @property {number} total
 * @property {number} page
 * @property {number} totalPages
 * @property {{ values: Record<string, Record<string, number>>, price: {min:number,max:number} }} facets
 */

/**
 * @typedef {Object} Order
 * @property {string} orderNumber
 * @property {string} createdAt
 * @property {'pending'|'processing'|'shipped'|'delivered'} status
 * @property {CartLine[]} items
 * @property {{ firstName:string, lastName:string, phone:string, city:string, address:string, comment?:string }} customer
 * @property {{ subtotal:number, shipping:number, total:number }} totals
 * @property {string} paymentMethod
 */

/**
 * @typedef {Object} User
 * @property {string} id
 * @property {string} firstName
 * @property {string} lastName
 * @property {string} email
 * @property {string} [phone]
 * @property {string} createdAt
 */

export {};
