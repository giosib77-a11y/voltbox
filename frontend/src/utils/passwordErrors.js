import { t } from '../i18n/index.js';

/**
 * The words for a server refusal of a new password, or null when the error is
 * not about that field.
 *
 * The browser checks only the length (validate.js); the server also refuses a
 * password from the list of common ones and a repetition or simple sequence,
 * and an administrator's needs 12 characters. All of these come back as an
 * error on the password field, which a page shows next to that field instead of
 * only in a toast. Same shape in `http` mode; the mock API raises none of them.
 *
 * `field` is the request's camelCase name: `password` (register) or
 * `newPassword` (change / reset). The reason is told apart by the server's
 * message text, the only part of the entry that names it (its `type` is the
 * same `value_error` for both). A refusal on the field for any other reason
 * (e.g. longer than 128 characters) gets the general "not accepted, choose
 * another" text, still at the field. A page that gets a text back shows it at
 * the field and shows no generic toast.
 */
export function passwordFieldError(error, field) {
  if (error?.details?.code === 'ADMIN_PASSWORD_TOO_SHORT') return error.message;

  const entries = error?.details?.details;
  if (!Array.isArray(entries)) return null;
  const entry = entries.find((e) => e?.field === field);
  if (!entry) return null;

  const message = String(entry.message || '');
  if (/too common/i.test(message)) return t('auth.tooCommon');
  if (/repetition|sequence/i.test(message)) return t('auth.tooPatterned');
  return t('auth.passwordRefused');
}
