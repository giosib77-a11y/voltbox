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

export const MESSAGES = {
  required: 'ეს ველი სავალდებულოა',
  firstName: 'შეიყვანეთ სახელი',
  lastName: 'შეიყვანეთ გვარი',
  phone: 'ტელეფონის ფორმატი: 5XX XX XX XX',
  email: 'შეიყვანეთ სწორი ელ. ფოსტა',
  city: 'აირჩიეთ ქალაქი',
  address: 'შეიყვანეთ მისამართი',
  addressShort: 'მისამართი ძალიან მოკლეა (მინ. 5 სიმბოლო)',
  password: `პაროლი უნდა იყოს მინიმუმ ${MIN_PASSWORD_LENGTH} სიმბოლო`,
  passwordMismatch: 'პაროლები არ ემთხვევა',
  nameShort: 'მინიმუმ 2 სიმბოლო',
  terms: 'გთხოვთ, დაეთანხმოთ პირობებს',
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
export const LOGIN_FIELDS = ['email', 'password'];
export const REGISTER_FIELDS = ['firstName', 'lastName', 'email', 'password', 'confirmPassword'];
export const PROFILE_FIELDS = ['firstName', 'lastName', 'email', 'phone'];
export const PASSWORD_FIELDS = ['currentPassword', 'newPassword', 'confirmPassword'];
export const ADDRESS_FIELDS = ['city', 'address'];
