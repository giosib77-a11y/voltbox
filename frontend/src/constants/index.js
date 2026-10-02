/**
 * ცენტრალიზებული კონფიგი.
 *
 * Interface text lives in src/i18n/ka.json and en.json; what stays here is
 * configuration, and for a list whose entries have words - sort options,
 * payment methods, order statuses - the values the words are keyed by.
 */

/* -------------------------------------------------------------------------- */
/*  ბრენდი / მეტა                                                              */
/* -------------------------------------------------------------------------- */

export const SITE_NAME = 'VoltBox';

export const CONTACT = {
  phone: '+995 322 00 11 22',
  phoneHref: 'tel:+995322001122',
  email: 'info@voltbox.ge',
  // The address and the working hours are words: `contact.*` in the
  // translation files.
};

/**
 * ფუტერის „ინფორმაციის“ ოთხი გვერდი — მისამართი და სათაურის გასაღები ერთად.
 *
 * ფუტერი ბმულს, App.jsx მარშრუტს, გვერდი კი სათაურს აქედან იღებს. ბმულები
 * ადრე კატეგორიებზე და მთავარ გვერდზე მიდიოდა, რადგან გვერდები არ არსებობდა.
 * The title is `t(titleKey)`; backend/tests/test_sitemap.py reads the paths.
 */
export const INFO_PAGES = {
  delivery: { path: '/delivery', titleKey: 'infoPages.delivery' },
  returns: { path: '/returns', titleKey: 'infoPages.returns' },
  privacy: { path: '/privacy', titleKey: 'infoPages.privacy' },
  faq: { path: '/faq', titleKey: 'infoPages.faq' },
};

/**
 * ფაქტები, რომლებსაც საინფორმაციო გვერდები მფლობელისგან ელოდება.
 *
 * `null` — ჯერ უცნობია, და წინადადება, რომელიც მას ეყრდნობა, საერთოდ არ ჩანს:
 * ცარიელი ადგილი ან „მალე“ მყიდველს დაპირებას ჰგავს. მნიშვნელობის ჩაწერა
 * წინადადებას თავისით აჩენს — რა ჩაიწეროს და რა ფორმით, იხ.
 * docs/info-pages-todo.md.
 */
export const SHOP_FACTS = {
  // დაბრუნების მე-2 ნაბიჯი, მთლიანი წინადადება
  returnPickup: null,
  // „პროდუქტზე ვრცელდება გარანტია, ვადით {warrantyPeriod}.“ — მაგ. 'ერთი წელი'
  warrantyPeriod: null,
  // „ვინ ვართ“ — { name, idCode, address }
  legalEntity: null,
};

/* -------------------------------------------------------------------------- */
/*  localStorage გასაღებები (ვერსიით — მიგრაციისთვის)                          */
/* -------------------------------------------------------------------------- */

export const STORAGE_KEYS = {
  cart: 'cart:v1',
  auth: 'auth:v1',
  users: 'users:v1',
  orders: 'orders:v1',
  addresses: 'addresses:v1',
  recentSearches: 'recent-searches:v1',
  theme: 'theme:v1',
};

/* -------------------------------------------------------------------------- */
/*  ფასდაკლება / მიწოდება                                                      */
/* -------------------------------------------------------------------------- */

export const CURRENCY_SYMBOL = '₾';

/*
 * მიწოდების ვადა — მხოლოდ ტექსტი, `shipping.etaDays` თარგმანის ფაილებში.
 * ერთადერთი წყარო: კალათა, პროდუქტის გვერდი, შეკვეთის დადასტურება და
 * საინფორმაციო გვერდები ყველა ამას კითხულობს.
 *
 * ფასები აქ აღარ არის: ქალაქები, ტარიფები და უფასო მიწოდების ზღვარი
 * backend-ის app/services/delivery.py-შია და `GET /delivery`-ით მოდის
 * (hooks/useDeliveryRules.js). საკუთარი ასლი აქ რომ ყოფილიყო, კალათა ერთ ფასს
 * აჩვენებდა, სერვერი კი მეორეს ჩამოაჭრიდა.
 */

/** მარაგის ზღვარი, რომლის ქვემოთაც ვწერთ "ბოლო ცალები". */
export const LOW_STOCK_THRESHOLD = 3;

/* -------------------------------------------------------------------------- */
/*  კატალოგი                                                                   */
/* -------------------------------------------------------------------------- */

export const PAGE_SIZE = 12;

/** Each one's label is `t('sort.<value>')`. */
export const SORT_OPTIONS = ['popular', 'newest', 'price_asc', 'price_desc', 'rating'];

export const DEFAULT_SORT = 'popular';

/** query-პარამეტრების სახელები. */
export const QUERY_KEYS = {
  search: 'q',
  sort: 'sort',
  page: 'page',
  price: 'price',
  redirect: 'redirect',
};

/* -------------------------------------------------------------------------- */
/*  specs                                                                      */
/* -------------------------------------------------------------------------- */

/*
 * A spec key's label is `specs.<key>` in the translation files; a key with no
 * entry there is shown as it is. BOOLEAN_LABELS, which said the same as
 * formatSpecValue and was imported by nothing, is gone.
 */

/* -------------------------------------------------------------------------- */
/*  გადახდა (checkout)                                                        */
/* -------------------------------------------------------------------------- */

/**
 * ყველა მეთოდი, რომლითაც შეკვეთა შეიძლება იყოს შენახული — ლეიბლი `payment.<value>`.
 * `offered: false` checkout-ში აღარ ჩანს (API მას ახალ შეკვეთაზე 400-ით
 * უარყოფს), მაგრამ ძველი შეკვეთის გვერდმა ის მაინც უნდა დაასახელოს.
 * backend-ის PAYMENT_METHODS / OFFERED_PAYMENT_METHODS-ს ამოწმებს
 * backend/tests/test_payment_methods.py.
 */
export const PAYMENT_METHODS = [
  { value: 'cash', offered: true },
  { value: 'card_on_delivery', offered: false },
];

/** რასაც checkout სთავაზობს. */
export const OFFERED_PAYMENT_METHODS = PAYMENT_METHODS.filter((method) => method.offered);

/**
 * შეკვეთის სტატუსი მყიდველის ენაზე — ექვსივე (ტონი აქ, სიტყვა `orderStatus.*`).
 *
 * ექვსივე იმიტომ, რომ სერვერს ექვსი აქვს (app/services/order_status.py). სიაში
 * ოთხი იყო და `confirmed`-იც და `cancelled`-იც `pending`-ზე ვარდებოდა — ანუ
 * გაუქმებულ შეკვეთას მყიდველისთვის ეწერა, რომ მუშავდება.
 *
 * ერთ ადგილას, რომ ორმა გვერდმა ერთი და იგივე თქვას. ადმინის ფორმულირება სხვაა
 * (src/admin/statuses.jsx) — იქ მაღაზიის თანამშრომელი კითხულობს.
 */
export const ORDER_STATUS_TONES = {
  pending: 'warning',
  confirmed: 'warning',
  processing: 'warning',
  shipped: 'neutral',
  delivered: 'success',
  cancelled: 'danger',
};

/**
 * A status as the page shows it: `{ label, tone }`, the label `orderStatus.*`.
 * უცნობი სტატუსი არაფერს ამბობს — გამოცნობით დაიწერა ერთხელ „მუშავდება“ გაუქმებულზე.
 */
export function orderStatus(status, t) {
  const tone = ORDER_STATUS_TONES[status];
  return tone ? { label: t(`orderStatus.${status}`), tone } : { label: '—', tone: 'neutral' };
}
