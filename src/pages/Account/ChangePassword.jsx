import { useState } from 'react';
import { KeyRound } from 'lucide-react';
import Button from '../../components/common/Button.jsx';
import Input from '../../components/common/Input.jsx';
import { useAuth } from '../../hooks/useAuth.js';
import { useToast } from '../../hooks/useToast.js';
import { useDocumentTitle } from '../../hooks/useDocumentTitle.js';
import { MIN_PASSWORD_LENGTH, PASSWORD_FIELDS, validateField, validateForm } from '../../utils/validate.js';

const EMPTY = { currentPassword: '', newPassword: '', confirmPassword: '' };

// MOCK ONLY — replace with real auth API.
export default function ChangePassword() {
  useDocumentTitle('პაროლის შეცვლა');

  const { changePassword } = useAuth();
  const toast = useToast();

  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [saving, setSaving] = useState(false);

  function handleChange(name, value) {
    const next = { ...values, [name]: value };
    setValues(next);
    if (touched[name]) setErrors((c) => ({ ...c, [name]: validateField(name, value, next) }));
  }

  function handleBlur(name) {
    setTouched((c) => ({ ...c, [name]: true }));
    setErrors((c) => ({ ...c, [name]: validateField(name, values[name], values) }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validateForm(values, PASSWORD_FIELDS);
    setErrors(nextErrors);
    setTouched(Object.fromEntries(PASSWORD_FIELDS.map((f) => [f, true])));
    if (Object.keys(nextErrors).length > 0) return;

    setSaving(true);
    try {
      await changePassword({
        currentPassword: values.currentPassword,
        newPassword: values.newPassword,
      });
      setValues(EMPTY);
      setTouched({});
      toast.success('პაროლი შეიცვალა');
    } catch (error) {
      toast.error(error?.message || 'პაროლის შეცვლა ვერ მოხერხდა');
      if (error?.details?.currentPassword) {
        setErrors({ currentPassword: error.message });
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="max-w-md rounded-card border border-ink-200 bg-white p-5 sm:p-6">
      <h2 className="text-base font-bold text-ink-900">პაროლის შეცვლა</h2>
      <p className="mt-1 text-sm text-ink-600">
        ახალი პაროლი უნდა შეიცავდეს მინიმუმ {MIN_PASSWORD_LENGTH} სიმბოლოს.
      </p>

      <div className="mt-5 space-y-4">
        <Input
          label="მიმდინარე პაროლი"
          type="password"
          required
          autoComplete="current-password"
          value={values.currentPassword}
          error={touched.currentPassword ? errors.currentPassword : ''}
          onChange={(e) => handleChange('currentPassword', e.target.value)}
          onBlur={() => handleBlur('currentPassword')}
        />
        <Input
          label="ახალი პაროლი"
          type="password"
          required
          autoComplete="new-password"
          value={values.newPassword}
          error={touched.newPassword ? errors.newPassword : ''}
          onChange={(e) => handleChange('newPassword', e.target.value)}
          onBlur={() => handleBlur('newPassword')}
        />
        <Input
          label="გაიმეორეთ ახალი პაროლი"
          type="password"
          required
          autoComplete="new-password"
          value={values.confirmPassword}
          error={touched.confirmPassword ? errors.confirmPassword : ''}
          onChange={(e) => handleChange('confirmPassword', e.target.value)}
          onBlur={() => handleBlur('confirmPassword')}
        />
      </div>

      <Button type="submit" className="mt-6" loading={saving}>
        <KeyRound className="h-4 w-4" aria-hidden="true" />
        პაროლის განახლება
      </Button>
    </form>
  );
}
