/**
 * Tests for the form rules.
 *
 * Every form on the shop asks this module whether what somebody typed is
 * acceptable, and it had no tests at all - 0% of the file was covered. That is
 * the wrong place for a blind spot: a rule that is too strict turns a real
 * customer away at checkout, and one that is too loose sends the API something
 * it will reject with a message written for a developer.
 *
 * The phone pattern is checked against the backend's own regex, because the two
 * have to agree exactly. A number the form accepts and the API refuses is a 400
 * arriving after the shopper has already filled everything in.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  CHECKOUT_FIELDS,
  MESSAGES,
  MIN_PASSWORD_LENGTH,
  PHONE_PATTERN,
  REGISTER_FIELDS,
  digitsOnly,
  isRequired,
  isValidEmail,
  isValidPhone,
  validateField,
  validateForm,
} from './validate.js';

describe('a Georgian mobile number', () => {
  it.each([
    ['555123456', 'plain'],
    ['555 12 34 56', 'the way it is printed'],
    ['555-12-34-56', 'with dashes'],
    ['(555) 123456', 'with brackets'],
  ])('accepts %s (%s)', (value) => {
    expect(isValidPhone(value)).toBe(true);
  });

  it.each([
    ['995555123456', 'the country code as digits'],
    ['+995 555 12 34 56', 'the country code as written'],
    ['12345678', 'a landline'],
    ['55512345', 'one digit short'],
    ['5551234567', 'one digit too many'],
    ['', 'nothing'],
    [null, 'null'],
  ])('refuses %s (%s)', (value) => {
    expect(isValidPhone(value)).toBe(false);
  });

  it('agrees exactly with the pattern the API enforces', () => {
    // app/schemas/order.py: phone: str = Field(pattern=r"^5\d{8}$")
    const schema = readFileSync(
      join(process.cwd(), '..', 'backend', 'app', 'schemas', 'order.py'),
      'utf8',
    );
    const backend = schema.match(/phone: str = Field\(pattern=r"([^"]+)"/)?.[1];

    expect(backend, 'the phone field moved; this test needs updating').toBeTruthy();
    expect(PHONE_PATTERN.source).toBe(backend);
  });

  it('is why the form sends digits and not what was typed', () => {
    // Checkout calls digitsOnly() before posting. Without that the API would
    // see "555 12 34 56" and refuse a number the form had just accepted.
    expect(digitsOnly('555 12 34 56')).toBe('555123456');
    expect(PHONE_PATTERN.test(digitsOnly('555 12 34 56'))).toBe(true);
    expect(PHONE_PATTERN.test('555 12 34 56')).toBe(false);
  });
});

describe('an email address', () => {
  it.each(['nino@example.ge', 'a.b+c@sub.domain.co.uk', ' spaced@example.ge '])(
    'accepts %s',
    (value) => expect(isValidEmail(value)).toBe(true),
  );

  it.each(['nino', 'nino@', '@example.ge', 'nino@example', 'a b@example.ge', ''])(
    'refuses %s',
    (value) => expect(isValidEmail(value)).toBe(false),
  );
});

describe('a required value', () => {
  it.each([['x'], [' x '], [0], [['a']]])('accepts %s', (value) =>
    expect(isRequired(value)).toBe(true),
  );

  it('does not accept whitespace as an answer', () => {
    expect(isRequired('   ')).toBe(false);
    expect(isRequired('')).toBe(false);
    expect(isRequired(null)).toBe(false);
    expect(isRequired([])).toBe(false);
  });
});

describe('field by field', () => {
  it('wants a name of at least two letters', () => {
    expect(validateField('firstName', '')).toBe(MESSAGES.firstName);
    expect(validateField('firstName', 'ნ')).toBe(MESSAGES.nameShort);
    expect(validateField('firstName', 'ნინო')).toBe('');
  });

  it('wants an address somebody could deliver to', () => {
    // Five characters is not much, but "აბც" is not an address.
    expect(validateField('address', '')).toBe(MESSAGES.address);
    expect(validateField('address', 'აბც')).toBe(MESSAGES.addressShort);
    expect(validateField('address', 'აღმაშენებლის 120')).toBe('');
  });

  it('enforces the same password length the API does', () => {
    expect(validateField('password', 'x'.repeat(MIN_PASSWORD_LENGTH - 1))).toBe(MESSAGES.password);
    expect(validateField('password', 'x'.repeat(MIN_PASSWORD_LENGTH))).toBe('');
  });

  it('checks the confirmation against whichever password the form has', () => {
    // Registration calls it `password`, changing a password calls it
    // `newPassword`. Both forms use this one rule.
    expect(validateField('confirmPassword', 'abcdefgh', { password: 'abcdefgh' })).toBe('');
    expect(validateField('confirmPassword', 'abcdefgh', { newPassword: 'abcdefgh' })).toBe('');
    expect(validateField('confirmPassword', 'abcdefgh', { password: 'different' })).toBe(
      MESSAGES.passwordMismatch,
    );
  });

  it('says nothing about a field it does not know', () => {
    expect(validateField('nickname', '')).toBe('');
  });
});

describe('a whole form', () => {
  it('refuses an empty checkout and names every missing field', () => {
    const errors = validateForm({}, CHECKOUT_FIELDS);

    expect(Object.keys(errors).sort()).toEqual(
      ['address', 'city', 'firstName', 'lastName', 'phone'].sort(),
    );
  });

  it('passes a checkout somebody actually filled in', () => {
    const errors = validateForm(
      {
        firstName: 'ნინო',
        lastName: 'კაპანაძე',
        phone: '555 12 34 56',
        city: 'თბილისი',
        address: 'აღმაშენებლის 120, ბინა 7',
      },
      CHECKOUT_FIELDS,
    );

    expect(errors).toEqual({});
  });

  it('catches a mismatched confirmation during registration', () => {
    const errors = validateForm(
      {
        firstName: 'ნინო',
        lastName: 'კაპანაძე',
        email: 'nino@example.ge',
        password: 'Mountain-River-42',
        confirmPassword: 'Mountain-River-43',
      },
      REGISTER_FIELDS,
    );

    expect(errors).toEqual({ confirmPassword: MESSAGES.passwordMismatch });
  });
});
