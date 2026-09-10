/**
 * ძებნის ერთადერთი ადგილი.
 *
 * Backend-ზე გადასვლისას მხოლოდ ეს ფაილი კარგავს გამოძახებას (server-side
 * search-ის სასარგებლოდ) — UI-ს არაფერი ეცვლება.
 *
 * ალგორითმი:
 *   1. ნორმალიზაცია  — lowercase, პუნქტუაცია, ათასეულების გამყოფები, ერთეულები.
 *   2. ტოკენიზაცია   — AND ტოკენებზე, OR ველებზე.
 *   3. რანჟირება     — name 10 > brand 6 > category 5 > specs 4 > tags 3 >
 *                      shortDescription 2 > description 1 (+ ზუსტი დამთხვევის ბონუსი).
 */

/* -------------------------------------------------------------------------- */
/*  1. ნორმალიზაცია                                                            */
/* -------------------------------------------------------------------------- */

/** ერთეულების უნიფიკაცია — ქართული და ინგლისური ვარიანტები ერთ ფორმაზე. */
const UNIT_ALIASES = {
  mah: 'mah', mahs: 'mah', 'მაჰ': 'mah', 'მაh': 'mah',
  m: 'm', meter: 'm', meters: 'm', metre: 'm', 'მ': 'm', 'მეტრი': 'm', 'მეტრიანი': 'm',
  sm: 'sm', cm: 'sm', 'სმ': 'sm', 'სანტიმეტრი': 'sm',
  mm: 'mm', 'მმ': 'mm',
  gb: 'gb', gbs: 'gb', gigabyte: 'gb', gigabytes: 'gb', 'გბ': 'gb', 'გიგაბაიტი': 'gb',
  tb: 'tb', terabyte: 'tb', 'ტბ': 'tb',
  w: 'w', watt: 'w', watts: 'w', 'ვტ': 'w', 'ვატი': 'w', 'ვატ': 'w',
  v: 'v', volt: 'v', 'ვ': 'v',
  a: 'a', amp: 'a', amps: 'a', ampere: 'a',
  hz: 'hz', 'ჰც': 'hz',
  mp: 'mp', 'მპ': 'mp', megapixel: 'mp',
  h: 'h', hr: 'h', hrs: 'h', hour: 'h', hours: 'h', 'სთ': 'h', 'საათი': 'h',
  in: 'in', inch: 'in', inches: 'in', 'დიუიმი': 'in',
};

const UNIT_KEYS = Object.keys(UNIT_ALIASES).sort((a, b) => b.length - a.length);
const UNIT_SUFFIX_RE = new RegExp('^([0-9]+(?:[.][0-9]+)?)(' + UNIT_KEYS.join('|') + ')$', 'i');

/**
 * ტექსტს აქცევს შედარებად, სივრცით გამოყოფილ ტოკენებად.
 * ერთი ველი = ერთი გამოძახება (ათასეულების შერწყმა ველებს შორის არ გადადის).
 */
export function normalize(input) {
  let s = String(input ?? '').toLowerCase();

  // ინჩის ნიშანი ციფრის შემდეგ: 6.2" → 6.2 in
  s = s.replace(/(\d)\s*["″]/g, '$1 in');

  // ათასეულების მძიმე: 20,000 → 20000
  s = s.replace(/(\d),(?=\d{3}\b)/g, '$1');

  // წერტილი მხოლოდ ციფრებს შორის რჩება (6.2), დანარჩენი პუნქტუაცია → სივრცე
  s = s.replace(/\.(?!\d)/g, ' ').replace(/(?<!\d)\./g, ' ');
  s = s.replace(/[^\p{L}\p{N}. ]+/gu, ' ');

  // ათასეულების სივრცე: 20 000 → 20000 (მხოლოდ ზუსტად 3-ციფრიანი ჯგუფი,
  // რომელსაც ასო არ მოსდევს — რომ "15 128gb" არ გაერთიანდეს)
  s = s.replace(/(\d)\s+(\d{3})(?![\d\p{L}])/gu, '$1$2');

  // რიცხვისა და ერთეულის გაყოფა: 20000mah → 20000 mah, 2მ → 2 m
  s = s
    .split(/\s+/)
    .flatMap((word) => {
      const m = word.match(UNIT_SUFFIX_RE);
      if (m) return [m[1], UNIT_ALIASES[m[2]] || m[2]];
      return [UNIT_ALIASES[word] || word];
    })
    .filter(Boolean)
    .join(' ');

  return s.trim().replace(/\s+/g, ' ');
}

/* -------------------------------------------------------------------------- */
/*  2. ტოკენიზაცია და მორფოლოგია                                               */
/* -------------------------------------------------------------------------- */

/** ქართული ბრუნვა/მრავლობითის დაბოლოებები — გრძელიდან მოკლისკენ. */
const KA_SUFFIXES = [
  'ებისთვის', 'ებისგან', 'ებიდან', 'ებამდე', 'ებში', 'ებზე', 'ებით', 'ების', 'ებს', 'ები',
  'ისთვის', 'ისგან', 'იდან', 'ამდე', 'ში', 'ზე', 'ით', 'ის', 'ს', 'ი',
];

/** უხეში, მაგრამ საკმარისი სტემინგი: „ყურსასმენები“ და „ყურსასმენი“ → „ყურსასმენ“. */
export function stem(word) {
  if (!word || word.length < 5) return word;
  for (const suffix of KA_SUFFIXES) {
    if (word.length - suffix.length >= 4 && word.endsWith(suffix)) {
      return word.slice(0, -suffix.length);
    }
  }
  return word;
}

const NUMERIC_TOKEN = /^[0-9]+([.][0-9]+)?$/;

export function tokenize(query) {
  return normalize(query).split(' ').filter(Boolean);
}

/**
 * ერთი ტოკენის შედარება ერთ ველთან.
 * @returns {number} 0 = არ ემთხვევა, 1 = ნაწილობრივი, 1.2 = პრეფიქსი, 1.5 = ზუსტი
 */
export function matchStrength(fieldText, token) {
  if (!fieldText || !token) return 0;

  // წმინდა რიცხვითი ტოკენი მხოლოდ ზუსტად ემთხვევა: "2" არ არის "24" და არც "240";
  // ასევე 1–2 სიმბოლოიანი ტოკენი ("c", "m", "5g") — თორემ "m" დაემთხვევა "mah"-ს
  if (NUMERIC_TOKEN.test(token) || token.length <= 2) {
    return fieldText.split(" ").includes(token) ? 1.5 : 0;
  }

  const words = fieldText.split(' ');
  const tokenStem = stem(token);

  let best = 0;
  for (const word of words) {
    if (word === token) return 1.5;
    if (word.startsWith(token)) best = Math.max(best, 1.2);
    else if (tokenStem.length >= 4) {
      const wordStem = stem(word);
      if (wordStem === tokenStem) best = Math.max(best, 1.4);
      else if (wordStem.startsWith(tokenStem)) best = Math.max(best, 1.15);
    }
  }
  // ≥3 სიმბოლოზე ვუშვებთ ქვესტრიქონსაც (მაგ. "amoled" → "superamoled")
  if (best === 0 && token.length >= 3 && fieldText.includes(token)) best = 1;
  return best;
}

/* -------------------------------------------------------------------------- */
/*  3. ინდექსი და რანჟირება                                                    */
/* -------------------------------------------------------------------------- */

export const FIELD_WEIGHTS = {
  name: 10,
  brand: 6,
  category: 5,
  specs: 4,
  tags: 3,
  shortDescription: 2,
  description: 1,
};

/** პროდუქტის ნორმალიზებული ინდექსი — იქმნება ერთხელ და ქეშირდება. */
const indexCache = new WeakMap();

export function buildIndex(product, categoryLabel = '') {
  const cached = indexCache.get(product);
  if (cached && cached.categoryLabel === categoryLabel) return cached;

  const specValues = Object.entries(product.specs || {})
    .map(([key, value]) => `${key} ${value === true ? 'დიახ' : value === false ? 'არა' : value}`)
    .join(' ');

  const index = {
    categoryLabel,
    fields: {
      name: normalize(product.name),
      brand: normalize(product.brand),
      category: normalize(`${product.category} ${categoryLabel}`),
      specs: normalize(specValues),
      tags: normalize((product.tags || []).join(' ')),
      shortDescription: normalize(product.shortDescription),
      description: normalize(product.description),
    },
  };
  index.all = Object.values(index.fields).join(' | ');
  indexCache.set(product, index);
  return index;
}

/**
 * ერთი პროდუქტის ქულა მოცემულ ტოკენებზე.
 * @returns {number} 0 — თუ თუნდაც ერთი ტოკენი არსად მოიძებნა (AND ლოგიკა).
 */
export function scoreProduct(product, tokens, categoryLabel = '', rawQuery = '') {
  if (!tokens.length) return 0;
  const index = buildIndex(product, categoryLabel);

  let total = 0;
  for (const token of tokens) {
    let tokenScore = 0;
    for (const [field, weight] of Object.entries(FIELD_WEIGHTS)) {
      const strength = matchStrength(index.fields[field], token);
      if (strength > 0) tokenScore += weight * strength;
    }
    if (tokenScore === 0) return 0; // AND: ყველა ტოკენი უნდა დაემთხვეს
    total += tokenScore;
  }

  // ბონუსები
  const normalizedQuery = normalize(rawQuery);
  if (normalizedQuery && index.fields.name === normalizedQuery) total += 60;
  else if (normalizedQuery && index.fields.name.startsWith(normalizedQuery)) total += 30;
  else if (normalizedQuery && index.fields.name.includes(normalizedQuery)) total += 15;

  if (product.inStock !== false && product.stock > 0) total += 2;
  total += Math.min(Number(product.rating) || 0, 5) * 0.4;

  return total;
}

/**
 * პროდუქტების ძებნა.
 * @param {Array} products
 * @param {string} query
 * @param {{ limit?: number, categoryLabels?: Record<string,string> }} [options]
 * @returns {Array} რანჟირებული პროდუქტები
 */
export function searchProducts(products, query, options = {}) {
  const { limit, categoryLabels = {} } = options;
  const tokens = tokenize(query);
  if (!tokens.length) return [];

  const scored = [];
  for (const product of products) {
    const score = scoreProduct(product, tokens, categoryLabels[product.category] || '', query);
    if (score > 0) scored.push({ product, score });
  }

  scored.sort((a, b) => b.score - a.score || a.product.name.localeCompare(b.product.name, 'ka'));
  const result = scored.map((entry) => entry.product);
  return typeof limit === 'number' ? result.slice(0, limit) : result;
}
