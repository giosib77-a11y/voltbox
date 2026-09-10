import { DEFAULT_SORT, QUERY_KEYS } from '../constants/index.js';

/**
 * კატალოგის ფილტრაცია / სორტირება / პაგინაცია და facet-ების დათვლა.
 * ყველაფერი data-driven არის — `categories.js`-ის `filters` კონფიგზე დაყრდნობით.
 * ახალი კატეგორია/ფილტრი კოდის ცვლილებას არ საჭიროებს.
 */

/* -------------------------------------------------------------------------- */
/*  ველზე წვდომა                                                               */
/* -------------------------------------------------------------------------- */

/** "specs.ram" → product.specs.ram */
export function getFieldValue(product, key) {
  if (!product || !key) return undefined;
  return key.split('.').reduce((acc, part) => (acc == null ? undefined : acc[part]), product);
}

/** ფილტრის key → URL query პარამეტრი ("specs.ram" → "ram") */
export function paramForFilter(filterConfig) {
  if (filterConfig.param) return filterConfig.param;
  return filterConfig.key.split('.').pop();
}

/** toggle-ფილტრის „ჩართული“ მნიშვნელობა */
function toggleMatchValue(filterConfig) {
  return filterConfig.match !== undefined ? filterConfig.match : true;
}

/* -------------------------------------------------------------------------- */
/*  URL ↔ filters ობიექტი                                                      */
/* -------------------------------------------------------------------------- */

/**
 * URLSearchParams → ფილტრების ობიექტი.
 * @returns {Record<string, string[]|boolean|[number,number]>}
 */
export function parseFiltersFromParams(searchParams, categoryFilters = []) {
  const filters = {};

  categoryFilters.forEach((config) => {
    const param = paramForFilter(config);
    const raw = searchParams.get(param);
    if (raw === null || raw === '') return;

    if (config.type === 'toggle') {
      if (raw === '1' || raw === 'true') filters[config.key] = true;
      return;
    }
    const values = raw.split(',').map((v) => v.trim()).filter(Boolean);
    if (values.length) filters[config.key] = values;
  });

  const price = searchParams.get(QUERY_KEYS.price);
  if (price) {
    const [min, max] = price.split('-').map((n) => Number(n));
    if (Number.isFinite(min) && Number.isFinite(max) && max >= min) filters.price = [min, max];
  }

  return filters;
}

/**
 * ფილტრების ობიექტი → ბრტყელი query ჩანაწერები (URLSearchParams-ისთვის).
 */
export function serializeFilters(filters = {}, categoryFilters = []) {
  const entries = {};

  categoryFilters.forEach((config) => {
    const value = filters[config.key];
    if (value === undefined || value === null) return;
    const param = paramForFilter(config);

    if (config.type === 'toggle') {
      if (value === true) entries[param] = '1';
      return;
    }
    if (Array.isArray(value) && value.length) entries[param] = value.join(',');
  });

  if (Array.isArray(filters.price) && filters.price.length === 2) {
    entries[QUERY_KEYS.price] = `${filters.price[0]}-${filters.price[1]}`;
  }
  return entries;
}

/** რამდენი ფილტრია აქტიური (chip-ების და ღილაკის ბეჯისთვის) */
export function countActiveFilters(filters = {}) {
  return Object.entries(filters).reduce((sum, [key, value]) => {
    if (key === 'price') return sum + (Array.isArray(value) ? 1 : 0);
    if (value === true) return sum + 1;
    return sum + (Array.isArray(value) ? value.length : 0);
  }, 0);
}

/* -------------------------------------------------------------------------- */
/*  ფილტრაცია                                                                  */
/* -------------------------------------------------------------------------- */

function matchesFilter(product, config, value) {
  if (value === undefined || value === null) return true;
  const fieldValue = getFieldValue(product, config.key);

  if (config.type === 'toggle') {
    if (value !== true) return true;
    return String(fieldValue) === String(toggleMatchValue(config));
  }

  if (!Array.isArray(value) || value.length === 0) return true;
  if (fieldValue === undefined || fieldValue === null) return false;

  if (Array.isArray(fieldValue)) {
    return fieldValue.some((v) => value.includes(String(v)));
  }
  return value.includes(String(fieldValue));
}

function matchesPrice(product, range) {
  if (!Array.isArray(range) || range.length !== 2) return true;
  const [min, max] = range;
  return product.price >= min && product.price <= max;
}

/**
 * ყველა ფილტრის გამოყენება.
 * @param {Array} products
 * @param {object} filters
 * @param {Array} categoryFilters კატეგორიის კონფიგი
 * @param {string} [skipKey] გამოსატოვებელი key (facet-ების დათვლისთვის)
 */
export function applyFilters(products, filters = {}, categoryFilters = [], skipKey = null) {
  const configs = categoryFilters.filter((c) => c.key !== skipKey);
  return products.filter((product) => {
    for (const config of configs) {
      if (!matchesFilter(product, config, filters[config.key])) return false;
    }
    if (skipKey !== 'price' && !matchesPrice(product, filters.price)) return false;
    return true;
  });
}

/* -------------------------------------------------------------------------- */
/*  Facet counts                                                               */
/* -------------------------------------------------------------------------- */

/** ბუნებრივი სორტირება: "8 GB" < "12 GB" < "256 GB" */
export function compareNatural(a, b) {
  const na = parseFloat(String(a).replace(',', '.'));
  const nb = parseFloat(String(b).replace(',', '.'));
  const aIsNum = !Number.isNaN(na) && /^[\d.,\s]/.test(String(a));
  const bIsNum = !Number.isNaN(nb) && /^[\d.,\s]/.test(String(b));
  if (aIsNum && bIsNum && na !== nb) return na - nb;
  return String(a).localeCompare(String(b), 'ka');
}

/**
 * თითოეული ოფციის ხელმისაწვდომი რაოდენობა.
 * count ითვლება ყველა *სხვა* ფილტრის გათვალისწინებით — სტანდარტული
 * e-commerce ქცევა, სადაც ერთი ჯგუფის შიგნით ოფციები არ ქრება.
 */
export function computeFacets(products, filters = {}, categoryFilters = []) {
  const values = {};

  categoryFilters.forEach((config) => {
    const pool = applyFilters(products, filters, categoryFilters, config.key);
    const counts = new Map();

    if (config.type === 'toggle') {
      const match = String(toggleMatchValue(config));
      counts.set(match, pool.filter((p) => String(getFieldValue(p, config.key)) === match).length);
    } else {
      // ყველა შესაძლო ოფცია სრული ნაკრებიდან (0-იანებიც ჩანს, disabled-ად)
      products.forEach((p) => {
        const raw = getFieldValue(p, config.key);
        if (raw === undefined || raw === null || raw === '') return;
        const list = Array.isArray(raw) ? raw : [raw];
        list.forEach((v) => {
          if (!counts.has(String(v))) counts.set(String(v), 0);
        });
      });
      pool.forEach((p) => {
        const raw = getFieldValue(p, config.key);
        if (raw === undefined || raw === null || raw === '') return;
        const list = Array.isArray(raw) ? raw : [raw];
        list.forEach((v) => counts.set(String(v), (counts.get(String(v)) || 0) + 1));
      });
    }

    values[config.key] = Object.fromEntries(
      [...counts.entries()].sort((a, b) => compareNatural(a[0], b[0])),
    );
  });

  const pricePool = applyFilters(products, filters, categoryFilters, 'price');
  const prices = pricePool.map((p) => p.price);
  const allPrices = products.map((p) => p.price);

  return {
    values,
    price: {
      min: allPrices.length ? Math.floor(Math.min(...allPrices)) : 0,
      max: allPrices.length ? Math.ceil(Math.max(...allPrices)) : 0,
      currentMin: prices.length ? Math.floor(Math.min(...prices)) : 0,
      currentMax: prices.length ? Math.ceil(Math.max(...prices)) : 0,
    },
  };
}

/* -------------------------------------------------------------------------- */
/*  სორტირება და პაგინაცია                                                     */
/* -------------------------------------------------------------------------- */

const SORTERS = {
  price_asc: (a, b) => a.price - b.price,
  price_desc: (a, b) => b.price - a.price,
  rating: (a, b) => b.rating - a.rating || b.reviewsCount - a.reviewsCount,
  newest: (a, b) => new Date(b.createdAt) - new Date(a.createdAt),
  // პოპულარობა: შეფასება × ლოგარითმული წონა შეფასებების რაოდენობაზე
  popular: (a, b) => popularityScore(b) - popularityScore(a),
};

function popularityScore(product) {
  return (Number(product.rating) || 0) * Math.log10((Number(product.reviewsCount) || 0) + 10);
}

export function sortProducts(products, sort = DEFAULT_SORT) {
  const sorter = SORTERS[sort] || SORTERS[DEFAULT_SORT];
  // მარაგში არმყოფი პროდუქტები ყოველთვის ბოლოში
  return [...products].sort((a, b) => {
    const stockDiff = (b.stock > 0 ? 1 : 0) - (a.stock > 0 ? 1 : 0);
    if (stockDiff !== 0) return stockDiff;
    return sorter(a, b);
  });
}

export function paginate(items, page = 1, limit = 12) {
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const safePage = Math.min(Math.max(1, Number(page) || 1), totalPages);
  const start = (safePage - 1) * limit;
  return {
    items: items.slice(start, start + limit),
    total,
    page: safePage,
    totalPages,
    limit,
  };
}

/**
 * აქტიური ფილტრების chip-ები — ცალ-ცალკე მოსახსნელად.
 * @returns {{ id:string, key:string, value:*, label:string, groupLabel:string }[]}
 */
const defaultChipLabel = (value, config) => config.optionLabels?.[value] ?? String(value);

export function buildFilterChips(filters = {}, categoryFilters = [], formatValue = defaultChipLabel) {
  const chips = [];

  categoryFilters.forEach((config) => {
    const value = filters[config.key];
    if (value === undefined || value === null) return;

    if (config.type === 'toggle') {
      if (value === true) {
        chips.push({
          id: `${config.key}:on`,
          key: config.key,
          value: true,
          groupLabel: config.label,
          label: config.label,
        });
      }
      return;
    }
    (Array.isArray(value) ? value : []).forEach((v) => {
      chips.push({
        id: `${config.key}:${v}`,
        key: config.key,
        value: v,
        groupLabel: config.label,
        label: formatValue(v, config),
      });
    });
  });

  if (Array.isArray(filters.price) && filters.price.length === 2) {
    chips.push({
      id: 'price',
      key: 'price',
      value: filters.price,
      groupLabel: 'ფასი',
      label: `${filters.price[0]} – ${filters.price[1]} ₾`,
    });
  }
  return chips;
}

/** ერთი მნიშვნელობის დამატება/მოხსნა (checkbox / swatch ლოგიკა). */
export function toggleFilterValue(filters, config, value) {
  const next = { ...filters };
  if (config.type === 'toggle') {
    if (next[config.key] === true) delete next[config.key];
    else next[config.key] = true;
    return next;
  }
  const current = Array.isArray(next[config.key]) ? next[config.key] : [];
  const exists = current.includes(value);
  const updated = exists ? current.filter((v) => v !== value) : [...current, value];
  if (updated.length) next[config.key] = updated;
  else delete next[config.key];
  return next;
}
