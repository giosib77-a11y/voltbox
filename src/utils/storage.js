/**
 * localStorage-ის უსაფრთხო wrapper.
 * ყველა წვდომა try/catch-შია: private mode, სავსე quota, გატეხილი JSON —
 * არცერთ შემთხვევაში აპლიკაცია არ უნდა ჩამოვარდეს.
 */

function hasStorage() {
  try {
    return typeof window !== 'undefined' && !!window.localStorage;
  } catch {
    return false;
  }
}

/**
 * @template T
 * @param {string} key
 * @param {T} fallback
 * @returns {T}
 */
export function readJSON(key, fallback) {
  if (!hasStorage()) return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null || raw === '') return fallback;
    const parsed = JSON.parse(raw);
    return parsed === null || parsed === undefined ? fallback : parsed;
  } catch {
    // გატეხილი ჩანაწერი — ვშლით, რომ მომდევნო ჩატვირთვაზე აღარ შეგვაწუხოს
    try {
      window.localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
    return fallback;
  }
}

export function writeJSON(key, value) {
  if (!hasStorage()) return false;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function removeKey(key) {
  if (!hasStorage()) return false;
  try {
    window.localStorage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}
