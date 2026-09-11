/**
 * Deciding whether a `?redirect=` value may be navigated to.
 *
 * What it does: returns the value when it is a path on this site, and the
 * fallback otherwise.
 * Where it fits: every page that reads a redirect or next parameter - Login,
 * Register and the admin login. The parameter reaches those pages from a link
 * anyone can write, which is what makes it untrusted.
 * Notes: the interesting part is that "starts with a slash" is not enough.
 * `//evil.com` is a protocol-relative URL and lands on another site; so does
 * `/\evil.com`, which browsers normalise to the same thing. And a browser
 * strips tabs and newlines out of a URL before resolving it, so a path with a
 * tab after the slash becomes `//evil.com` *after* this function has approved
 * it - unless control characters are rejected outright.
 *
 * The resolve-and-compare check at the end would catch most of these on its
 * own. It is kept together with the textual checks rather than instead of
 * them, because the two disagree exactly where browsers disagree with each
 * other, and the safe answer is for either to be able to refuse.
 */

/** Highest C0 control code; DEL sits at 0x7f, just above printable ASCII. */
const LAST_CONTROL = 0x1f;
const DELETE_CHAR = 0x7f;

/**
 * Written as codes rather than a character class: the literal characters are
 * invisible in source and get mangled by anything that rewrites the file.
 */
function hasControlCharacters(value) {
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    if (code <= LAST_CONTROL || code === DELETE_CHAR) return true;
  }
  return false;
}

/**
 * @param {unknown} raw value from the query string
 * @param {string} fallback where to go when it cannot be trusted
 * @returns {string} a same-origin `pathname + search + hash`, or `fallback`
 */
export function getSafeRedirect(raw, fallback = '/') {
  if (typeof raw !== 'string' || raw === '') return fallback;
  if (hasControlCharacters(raw)) return fallback;

  // One leading slash, and nothing that turns into a second one. A backslash
  // there is rejected for the same reason as a second slash: it leaves this
  // origin.
  if (!raw.startsWith('/')) return fallback;
  if (raw.startsWith('//') || raw.startsWith('/\\')) return fallback;

  const origin = globalThis.location?.origin;
  if (!origin) return fallback;

  let url;
  try {
    url = new URL(raw, origin);
  } catch {
    return fallback;
  }

  if (url.origin !== origin) return fallback;

  return `${url.pathname}${url.search}${url.hash}`;
}
