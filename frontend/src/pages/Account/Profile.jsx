import { useEffect, useState } from 'react';
import { Save } from 'lucide-react';
import Button from '../../components/common/Button.jsx';
import Input from '../../components/common/Input.jsx';
import { useAuth } from '../../hooks/useAuth.js';
import { useToast } from '../../hooks/useToast.js';
import { useDocumentTitle } from '../../hooks/useDocumentTitle.js';
import { formatPhone } from '../../utils/format.js';
import { digitsOnly, isValidPhone, MESSAGES, validateField, validateForm } from '../../utils/validate.js';

const FIELDS = ['firstName', 'lastName', 'email'];

export default function Profile() {
  useDocumentTitle('პროფილი');

  const { user, updateProfile } = useAuth();
  const toast = useToast();

  const [values, setValues] = useState({ firstName: '', lastName: '', email: '', phone: '' });
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    setValues({
      firstName: user.firstName || '',
      lastName: user.lastName || '',
      email: user.email || '',
      phone: user.phone ? formatPhone(user.phone) : '',
    });
  }, [user]);

  function handleChange(name, rawValue) {
    const value = name === 'phone' ? formatPhone(rawValue) : rawValue;
    setValues((c) => ({ ...c, [name]: value }));
    if (touched[name]) setErrors((c) => ({ ...c, [name]: validateFieldLocal(name, value) }));
  }

  function validateFieldLocal(name, value) {
    if (name === 'phone') {
      if (!value) return '';
      return isValidPhone(value) ? '' : MESSAGES.phone;
    }
    return validateField(name, value, values);
  }

  function handleBlur(name) {
    setTouched((c) => ({ ...c, [name]: true }));
    setErrors((c) => ({ ...c, [name]: validateFieldLocal(name, values[name]) }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validateForm(values, FIELDS);
    if (values.phone && !isValidPhone(values.phone)) nextErrors.phone = MESSAGES.phone;

    setErrors(nextErrors);
    setTouched({ firstName: true, lastName: true, email: true, phone: true });
    if (Object.keys(nextErrors).length > 0) return;

    setSaving(true);
    try {
      await updateProfile({
        firstName: values.firstName.trim(),
        lastName: values.lastName.trim(),
        email: values.email.trim().toLowerCase(),
        phone: digitsOnly(values.phone),
      });
      toast.success('პროფილი განახლდა');
    } catch (error) {
      toast.error(error?.message || 'შენახვა ვერ მოხერხდა');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="rounded-card border border-ink-200 bg-white p-5 sm:p-6">
      <h2 className="text-base font-bold text-ink-900">პირადი მონაცემები</h2>
      <p className="mt-1 text-sm text-ink-600">
        ეს მონაცემები ავტომატურად შეივსება შეკვეთის გაფორმებისას.
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Input
          label="სახელი"
          required
          value={values.firstName}
          error={touched.firstName ? errors.firstName : ''}
          onChange={(e) => handleChange('firstName', e.target.value)}
          onBlur={() => handleBlur('firstName')}
          autoComplete="given-name"
        />
        <Input
          label="გვარი"
          required
          value={values.lastName}
          error={touched.lastName ? errors.lastName : ''}
          onChange={(e) => handleChange('lastName', e.target.value)}
          onBlur={() => handleBlur('lastName')}
          autoComplete="family-name"
        />
        <Input
          label="ელ. ფოსტა"
          type="email"
          required
          value={values.email}
          error={touched.email ? errors.email : ''}
          onChange={(e) => handleChange('email', e.target.value)}
          onBlur={() => handleBlur('email')}
          autoComplete="email"
        />
        <Input
          label="ტელეფონი"
          inputMode="tel"
          placeholder="5XX XX XX XX"
          value={values.phone}
          error={touched.phone ? errors.phone : ''}
          onChange={(e) => handleChange('phone', e.target.value)}
          onBlur={() => handleBlur('phone')}
          autoComplete="tel"
        />
      </div>

      <Button type="submit" className="mt-6" loading={saving}>
        <Save className="h-4 w-4" aria-hidden="true" />
        შენახვა
      </Button>
    </form>
  );
}
