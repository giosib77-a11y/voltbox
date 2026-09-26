/**
 * Shared fetch client for every REST call the app makes.
 *
 * What it does: builds URLs, attaches the bearer token, turns the API's error
 * envelope into the project's error classes, and retries once after a token
 * refresh on 401.
 * Where it fits: httpApi.js (storefront) and admin/adminApi.js both sit on top
 * of it, so the refresh logic exists once and benefits both.
 * Notes: kept separate from httpApi.js so a mock-mode build can pull in the
 * admin API without also pulling in the storefront's http implementation.
 */

import {
  ApiError,
  AuthError,
  ConflictError,
  NotFoundError,
  SessionExpiredError,
  ValidationError,
} from './errors.js';
import { getAccessToken, isAuthPath, readSession, refreshSession } from './session.js';

const BASE_URL = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');

/**
 * How long to wait before giving up on a request, in milliseconds.
 *
 * Long, deliberately. A free-tier host puts the API to sleep after idling and
 * the first request afterwards waits for the process to start, so a tight
 * deadline would turn a slow first page into a failed one.
 */
const REQUEST_TIMEOUT_MS = 45_000;

/** An abort signal that fires after the deadline, where the browser has one. */
function timeoutSignal() {
  // Guarded: AbortSignal.timeout is recent enough that an older browser, or a
  // test environment, may not have it. Without it the request simply behaves
  // as it did before rather than throwing here.
  return typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
    ? AbortSignal.timeout(REQUEST_TIMEOUT_MS)
    : undefined;
}

/** ავტორიზაციის ტოკენი — რეალურ backend-ზე httpOnly cookie სჯობს. */
function authHeader() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Georgian text for the error codes whose server message is not user-facing.
 *
 * `code` is the stable part of the contract and `message` is written for a
 * developer reading a log. Everything the UI is in is Georgian, so the few
 * codes a shopper can actually trigger get a sentence that says what happened
 * and what to do about it.
 */
const CODE_MESSAGES = {
  RATE_LIMITED: 'ძალიან ბევრი მცდელობა იყო. დაელოდეთ ერთ წუთს და სცადეთ ხელახლა.',
  ADMIN_REQUIRED: 'ამ გვერდზე წვდომა მხოლოდ ადმინისტრატორს აქვს.',
  ACCOUNT_DISABLED: 'ანგარიში დაბლოკილია. დაუკავშირდით მაღაზიას.',
  INVALID_TOKEN: 'სესიის ვადა ამოიწურა. გთხოვთ, ხელახლა შეხვიდეთ.',
  EMAIL_ALREADY_EXISTS: 'ამ ელ. ფოსტით მომხმარებელი უკვე რეგისტრირებულია.',

  // The two a shopper meets most often. Both used to arrive in English —
  // "Invalid email or password" on every mistyped login, "Not enough stock"
  // when someone else took the last one first.
  INVALID_CREDENTIALS: 'ელ. ფოსტა ან პაროლი არასწორია.',
  TOO_MANY_LOGIN_ATTEMPTS: (details) => {
    const seconds = Number(details?.retryAfterSeconds);
    if (!Number.isFinite(seconds) || seconds <= 0) {
      return 'ზედიზედ ბევრი მცდელობა იყო. ცოტა ხანში სცადეთ ხელახლა.';
    }
    const minutes = Math.ceil(seconds / 60);
    return `ზედიზედ ბევრი მცდელობა იყო. სცადეთ ${minutes} წუთში.`;
  },
  INSUFFICIENT_STOCK: (details) => {
    const available = Number(details?.available);
    if (Number.isFinite(available) && available > 0) {
      return `მარაგში მხოლოდ ${available} ცალი დარჩა. შეამცირეთ რაოდენობა კალათაში.`;
    }
    return 'პროდუქტი მარაგში აღარ არის. წაშალეთ ის კალათიდან.';
  },

  PRODUCT_NOT_FOUND: 'პროდუქტი ვეღარ მოიძებნა — შესაძლოა წაიშალა.',
  CITY_NOT_SERVED: 'ამ ქალაქში მიწოდება ჯერ არ ხორციელდება. აირჩიეთ ქალაქი სიიდან.',
  PRODUCT_ARCHIVED: 'პროდუქტი დაარქივებულია.',
  ORDER_NOT_FOUND: 'ასეთი შეკვეთა ვერ მოიძებნა. შეამოწმეთ ნომერი და კონტაქტი.',
  ORDER_NOT_CANCELLABLE: 'ამ შეკვეთის გაუქმება ამ ეტაპზე შეუძლებელია.',
  INVALID_QUANTITY: 'მითითებული რაოდენობა დაუშვებელია.',
  INVALID_CURRENT_PASSWORD: 'მიმდინარე პაროლი არასწორია.',
  // The server text names an idempotency key, which means nothing to a shopper.
  IDEMPOTENCY_KEY_CONFLICT: 'კალათა შეიცვალა. განაახლეთ გვერდი და სცადეთ ხელახლა.',
  INVALID_IDEMPOTENCY_KEY: 'მოთხოვნა ვერ დამუშავდა. განაახლეთ გვერდი და სცადეთ ხელახლა.',
  IDEMPOTENCY_KEY_REQUIRED: 'მოთხოვნა ვერ დამუშავდა. განაახლეთ გვერდი და სცადეთ ხელახლა.',
  INVALID_REFRESH_TOKEN: 'სესიის ვადა ამოიწურა. გთხოვთ, ხელახლა შეხვიდეთ.',
  ADDRESS_NOT_FOUND: 'ეს მისამართი ვეღარ მოიძებნა.',
  CART_TOO_LARGE: 'კალათაში ძალიან ბევრი პროდუქტია. წაშალეთ რამდენიმე და სცადეთ ხელახლა.',

  // The generic ones. A 500 is the one anybody can meet, on any page, and it
  // used to arrive as the English "Internal server error" - the server's own
  // message is written for a log, not for the person reading the screen.
  INTERNAL_ERROR: 'სერვერზე მოულოდნელი შეცდომა მოხდა. სცადეთ ცოტა ხანში.',
  VALIDATION_ERROR: 'შეყვანილი მონაცემები არასწორია. შეამოწმეთ ველები.',
  NOT_FOUND: 'მოთხოვნილი გვერდი ან ჩანაწერი ვერ მოიძებნა.',
  UNAUTHORIZED: 'გასაგრძელებლად გთხოვთ შეხვიდეთ.',
  FORBIDDEN: 'ამ მოქმედების უფლება არ გაქვთ.',
  METHOD_NOT_ALLOWED: 'მოთხოვნა ვერ შესრულდა.',
  CONFLICT: 'მონაცემები შეიცვალა. განაახლეთ გვერდი და სცადეთ ხელახლა.',

  /* ------------------------------------------------------- ადმინ პანელი --- */
  // The panel shows these in a banner. The forms map a few of them onto their
  // own fields first (SKU_TAKEN next to the SKU box, and so on); these are the
  // words for every case that reaches the banner instead, which until now was
  // the server's English.
  PRODUCT_IN_USE: 'პროდუქტი შეკვეთებშია და წაშლა შეუძლებელია — გადაიტანეთ არქივში.',
  CATEGORY_IN_USE: 'კატეგორიაში პროდუქტებია. ჯერ გადაიტანეთ ისინი სხვაგან.',
  BRAND_IN_USE: 'ბრენდს პროდუქტები აქვს. ჯერ გადაიტანეთ ისინი სხვაგან.',
  ALREADY_ARCHIVED: 'პროდუქტი უკვე არქივშია.',
  NOT_ARCHIVED: 'პროდუქტი არქივში არაა.',
  CATEGORY_NOT_FOUND: 'კატეგორია ვერ მოიძებნა.',
  BRAND_NOT_FOUND: 'ბრენდი ვერ მოიძებნა.',
  CUSTOMER_NOT_FOUND: 'მომხმარებელი ვერ მოიძებნა.',
  PARENT_NOT_FOUND: 'მშობელი კატეგორია ვერ მოიძებნა.',
  CATEGORY_CYCLE: 'კატეგორია საკუთარ შვილში ვერ მოთავსდება.',
  CATEGORY_SELF_PARENT: 'კატეგორია საკუთარი თავის მშობელი ვერ იქნება.',
  CATEGORY_TOO_DEEP: 'ჩადგმა ძალიან ღრმაა.',
  SKU_TAKEN: 'ეს SKU სხვა პროდუქტს უკვე უკავია.',
  SLUG_TAKEN: 'ეს slug უკვე დაკავებულია.',
  INVALID_SLUG: 'slug არასწორია — გამოიყენეთ ლათინური ასოები, ციფრები და დეფისი.',
  INVALID_OLD_PRICE: 'ძველი ფასი მიმდინარეზე მაღალი უნდა იყოს.',
  BRAND_NAME_TAKEN: 'ასეთი ბრენდი უკვე არსებობს.',
  CANNOT_BLOCK_SELF: 'საკუთარი ანგარიშის დაბლოკვა შეუძლებელია.',
  CANNOT_BLOCK_ADMIN: 'ადმინისტრატორის დაბლოკვა პანელიდან შეუძლებელია.',
  INVALID_DATE: 'თარიღი არასწორია — ფორმატი: წწწწ-თთ-დდ.',

  // Stock
  EMPTY_ADJUSTMENT: 'ცვლილება ნულის ტოლი ვერ იქნება.',
  NOTE_REQUIRED: 'ამ მიზეზისთვის კომენტარი სავალდებულოა.',
  REASON_NOT_MANUAL: 'ეს მიზეზი ხელით არ ირჩევა — მას სისტემა წერს.',
  UNKNOWN_REASON: 'უცნობი მიზეზი.',
  UNKNOWN_SORT: 'უცნობი დალაგება.',
  UNKNOWN_STATUS: 'უცნობი სტატუსი.',
  INVALID_TRANSITION: 'ამ სტატუსიდან ასეთი გადასვლა შეუძლებელია.',

  // Images
  NO_IMAGES: 'სურათი არ აირჩა.',
  EMPTY_FILE: 'ფაილი ცარიელია.',
  INVALID_IMAGE: 'ფაილი სურათი არ არის.',
  // An iPhone saves photos as HEIC, and copied to a computer that is how they
  // arrive. It used to be "not an image", which gave no hint that the format is
  // what to change.
  UNSUPPORTED_IMAGE_FORMAT: (details) =>
    details?.detected === 'HEIC'
      ? 'ეს HEIC ფოტოა — iPhone სურათებს ამ ფორმატით ინახავს — და ის არ მიიღება. ' +
        'შეინახეთ JPEG-ად და ატვირთეთ ხელახლა.'
      : 'ასეთი ფორმატი არ მიიღება — გამოიყენეთ JPEG, PNG ან WebP.',
  // The two an admin meets with a photo their phone has just taken. Both used
  // to say only that something was wrong with it, which reads like the upload
  // is broken rather than like something to fix in three seconds.
  IMAGE_TOO_LARGE: (details) => {
    const bytes = Number(details?.maxBytes);
    if (!Number.isFinite(bytes) || bytes <= 0) {
      return 'სურათი ძალიან დიდია. შეინახეთ უფრო მცირე ზომით და სცადეთ ხელახლა.';
    }
    const limit = Math.round(bytes / (1024 * 1024));
    return `სურათი ${limit} MB-ზე დიდია. შეინახეთ უფრო მცირე ზომით და სცადეთ ხელახლა.`;
  },
  IMAGE_TOO_MANY_PIXELS: (details) => {
    const width = Number(details?.maxWidth);
    const height = Number(details?.maxHeight);
    // The size that would pass, in this photo's own proportions. Saying only
    // "too many pixels" leaves the admin guessing how much to cut.
    if (Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0) {
      return (
        `სურათს ძალიან ბევრი პიქსელი აქვს. შეამცირეთ ${width}×${height}-მდე და ატვირთეთ ხელახლა — ` +
        'საიტზე სურათი ისედაც 1600px-მდე მცირდება, ასე რომ ხარისხს ეს არაფერს დააკლებს.'
      );
    }
    return (
      'სურათს ძალიან ბევრი პიქსელი აქვს. ატვირთეთ უფრო მცირე ზომის სურათი — ტელეფონზე ' +
      '12 MP საკმარისია, საიტზე სურათი ისედაც 1600px-მდე მცირდება.'
    );
  },
  TOO_MANY_IMAGES: 'პროდუქტს ამაზე მეტი სურათი ვერ ექნება.',
  IMAGE_NOT_FOUND: 'სურათი ვერ მოიძებნა.',
  INCOMPLETE_IMAGE_ORDER: 'თანმიმდევრობაში ყველა სურათი უნდა იყოს ჩამოთვლილი.',
  STORAGE_UPLOAD_FAILED: 'სურათის ატვირთვა ვერ მოხერხდა. სცადეთ ხელახლა.',
  STORAGE_DELETE_FAILED: 'სურათი საცავიდან ვერ წაიშალა და ისევ ხელმისაწვდომია. სცადეთ ხელახლა.',
};

/**
 * Pulls message / code / details out of the backend's error envelope.
 *
 * The API always answers `{"error": {code, message, details}}`. The flat shape
 * is tolerated too so the client keeps working if an error ever comes from a
 * proxy or a middleware that does not use the envelope.
 */
function parseError(payload) {
  const envelope = payload?.error ?? payload ?? null;
  const code = envelope?.code || null;
  const details = envelope?.details ?? null;

  // A few codes carry something worth saying - how many are actually left, for
  // one - so an entry may be a function of the details rather than a sentence.
  const mapped = CODE_MESSAGES[code];
  const text = typeof mapped === 'function' ? mapped(details) : mapped;

  return {
    message: text || envelope?.message || 'მოთხოვნის დამუშავება ვერ მოხერხდა',
    code,
    details,
  };
}

/** query ობიექტი → search string (მასივები მძიმით). */
function toQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) {
      if (value.length) search.set(key, value.join(','));
    } else if (typeof value === 'object') {
      // filters: { brand: ['Apple'], 'specs.ram': ['8 GB'] } → brand=Apple&specs.ram=8 GB
      Object.entries(value).forEach(([k, v]) => {
        if (v === undefined || v === null) return;
        search.set(k, Array.isArray(v) ? v.join(',') : String(v));
      });
    } else {
      search.set(key, String(value));
    }
  });
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

/**
 * ერთიანი fetch wrapper — შეცდომებს იმავე კლასებად აქცევს, რასაც mock.
 *
 * 401-ზე ერთხელ ცდილობს access-ტოკენის განახლებას და მოთხოვნას იმეორებს.
 * `retried` შიდა დროშაა: მეორე 401 უკვე ნამდვილად უფლების პრობლემაა და არა
 * ვადაგასული ტოკენი — თორემ განახლება-გამეორების უსასრულო ციკლი დაიწყებოდა.
 */
export async function request(path, options = {}) {
  const { method = 'GET', body, params, signal, headers: extraHeaders, retried = false } = options;
  const url = `${BASE_URL}${path}${toQuery(params)}`;

  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

  let response;
  try {
    response = await fetch(url, {
      method,
      // A caller's own signal wins. Otherwise a default deadline, because
      // `fetch` has none: a server that accepts the connection and then never
      // answers leaves the spinner turning for as long as the tab is open, with
      // nothing to retry and nothing to read. Generous on purpose — the API
      // sleeps when idle on the current host and the first request after that
      // pays for the wake-up.
      signal: signal ?? timeoutSignal(),
      headers: {
        // FormData-ს boundary-ს ბრაუზერი თვითონ აყენებს — ხელით მითითება ტეხს
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        Accept: 'application/json',
        ...authHeader(),
        ...(extraHeaders || {}),
      },
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    });
  } catch (cause) {
    // A deadline that ran out and a connection that never opened are different
    // things to the reader: one is worth retrying now, the other means check
    // the connection.
    const message =
      cause?.name === 'TimeoutError'
        ? 'სერვერმა დროულად ვერ უპასუხა. სცადეთ ხელახლა.'
        : 'სერვერთან კავშირი ვერ დამყარდა';
    throw new ApiError(message, 0, cause);
  }

  // ვადაგასული ტოკენი: ერთი განახლება ყველა პარალელური მოთხოვნისთვის საერთოა
  // (`refreshSession` single-flight-ია), მერე თითოეული ზუსტად ერთხელ მეორდება.
  if (response.status === 401 && !retried && !isAuthPath(path)) {
    const hadSession = Boolean(readSession());
    const token = await refreshSession();
    if (token) return request(path, { ...options, retried: true });
    // The session is gone and `refreshSession` has already redirected. One
    // recognisable type for every request caught in the same moment, so the UI
    // shows one message rather than one per pending call. A guest falls
    // through instead: their 401 is about permission, not an expired session.
    if (hadSession) throw new SessionExpiredError();
  }

  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (response.ok) return payload;

  const { message, code, details } = parseError(payload);
  if (response.status === 404) throw new NotFoundError(message);
  if (response.status === 409) throw new ConflictError(message, { code, details });
  if (response.status === 401 || response.status === 403) {
    throw new AuthError(message, response.status, { code, details });
  }
  if (response.status === 422 || response.status === 400) {
    throw new ValidationError(message, { code, details }, response.status);
  }
  throw new ApiError(message, response.status, { code, details });
}

