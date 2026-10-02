import { t } from '../i18n/index.js';
/**
 * ფორმების ვალიდაცია. ყველა წესი აქ ცხოვრობს — კომპონენტები მხოლოდ
 * validateX(values) იძახებენ და იღებენ { field: 'შეცდომის ტექსტი' } ობიექტს.
 */

export const MIN_PASSWORD_LENGTH = 8;

/** ქართული მობილური: 5XX XX XX XX (9 ციფრი, იწყება 5-ით) */
export const PHONE_PATTERN = /^5\d{8}$/;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}$/;

export function digitsOnly(value) {
  return String(value ?? '').replace(/\D/g, '');
}

export function isRequired(value) {
  if (Array.isArray(value)) return value.length > 0;
  return String(value ?? '').trim().length > 0;
}

export function isValidPhone(value) {
  return PHONE_PATTERN.test(digitsOnly(value));
}

export function isValidEmail(value) {
  return EMAIL_PATTERN.test(String(value ?? '').trim());
}

/**
 * Each message in the page's language, read when it is asked for - getters,
 * so `MESSAGES.phone` keeps working for the callers and the tests that
 * compare against it.
 */
export const MESSAGES = {
  get required() { return t('validation.required'); },
  get firstName() { return t('validation.firstName'); },
  get lastName() { return t('validation.lastName'); },
  get phone() { return t('validation.phone'); },
  get email() { return t('validation.email'); },
  get city() { return t('validation.city'); },
  get address() { return t('validation.address'); },
  get addressShort() { return t('validation.addressShort'); },
  get password() { return t('validation.password', { count: MIN_PASSWORD_LENGTH }); },
  get passwordMismatch() { return t('validation.passwordMismatch'); },
  get nameShort() { return t('validation.nameShort'); },
  get terms() { return t('validation.terms'); },
};

/** ერთი ველის ვალიდაცია — blur-ზე inline შეცდომისთვის. */
export function validateField(name, value, allValues = {}) {
  switch (name) {
    case 'firstName':
      if (!isRequired(value)) return MESSAGES.firstName;
      if (String(value).trim().length < 2) return MESSAGES.nameShort;
      return '';
    case 'lastName':
      if (!isRequired(value)) return MESSAGES.lastName;
      if (String(value).trim().length < 2) return MESSAGES.nameShort;
      return '';
    case 'phone':
      if (!isRequired(value)) return MESSAGES.required;
      if (!isValidPhone(value)) return MESSAGES.phone;
      return '';
    case 'email':
      if (!isRequired(value)) return MESSAGES.required;
      if (!isValidEmail(value)) return MESSAGES.email;
      return '';
    case 'guestEmail':
      // არასავალდებულო — მაგრამ შევსებული სწორი უნდა იყოს, თორემ დადასტურება
      // არსად წავა, ან უცხოსთან
      if (!isRequired(value)) return '';
      if (!isValidEmail(value)) return MESSAGES.email;
      return '';
    case 'city':
      if (!isRequired(value)) return MESSAGES.city;
      return '';
    case 'address':
      if (!isRequired(value)) return MESSAGES.address;
      if (String(value).trim().length < 5) return MESSAGES.addressShort;
      return '';
    case 'password':
    case 'newPassword':
      if (!isRequired(value)) return MESSAGES.required;
      if (String(value).length < MIN_PASSWORD_LENGTH) return MESSAGES.password;
      return '';
    case 'currentPassword':
      if (!isRequired(value)) return MESSAGES.required;
      return '';
    case 'confirmPassword':
      if (!isRequired(value)) return MESSAGES.required;
      if (value !== (allValues.password ?? allValues.newPassword)) return MESSAGES.passwordMismatch;
      return '';
    default:
      return '';
  }
}

/** მთელი ფორმის ვალიდაცია მოცემული ველების სიით. */
export function validateForm(values, fields) {
  const errors = {};
  fields.forEach((name) => {
    const message = validateField(name, values[name], values);
    if (message) errors[name] = message;
  });
  return errors;
}

export const CHECKOUT_FIELDS = ['firstName', 'lastName', 'phone', 'city', 'address'];
/** სტუმარს ელფოსტასაც ვეკითხებით; შესულისა ანგარიშიდან ვიცით. */
export const GUEST_CHECKOUT_FIELDS = [...CHECKOUT_FIELDS, 'guestEmail'];
export const LOGIN_FIELDS = ['email', 'password'];
export const REGISTER_FIELDS = ['firstName', 'lastName', 'email', 'password', 'confirmPassword'];
export const PROFILE_FIELDS = ['firstName', 'lastName', 'email', 'phone'];
export const PASSWORD_FIELDS = ['currentPassword', 'newPassword', 'confirmPassword'];
export const RESET_PASSWORD_FIELDS = ['newPassword', 'confirmPassword'];
export const ADDRESS_FIELDS = ['city', 'address'];
