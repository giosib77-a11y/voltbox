import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { Eye, EyeOff, Mail, UserPlus } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import Input from '../components/common/Input.jsx';
import { useAuth } from '../hooks/useAuth.js';
import { useToast } from '../hooks/useToast.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { MIN_PASSWORD_LENGTH, REGISTER_FIELDS, validateField, validateForm } from '../utils/validate.js';
import { QUERY_KEYS } from '../constants/index.js';
import { getSafeRedirect } from '../utils/redirect.js';
import { t } from '../i18n/index.js';

const EMPTY = { firstName: '', lastName: '', email: '', password: '', confirmPassword: '' };

// MOCK ONLY — replace with real auth API.
export default function Register() {
  useDocumentTitle(t('auth.register'));

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Same untrusted parameter as on the login page, checked the same way.
  const redirectTo = getSafeRedirect(
    searchParams.get(QUERY_KEYS.redirect),
    '/account/orders',
  );

  const { register, pending } = useAuth();
  const toast = useToast();

  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [showPassword, setShowPassword] = useState(false);

  function handleChange(name, value) {
    const next = { ...values, [name]: value };
    setValues(next);
    if (touched[name]) setErrors((c) => ({ ...c, [name]: validateField(name, value, next) }));
    if (name === 'password' && touched.confirmPassword) {
      setErrors((c) => ({ ...c, confirmPassword: validateField('confirmPassword', next.confirmPassword, next) }));
    }
  }

  function handleBlur(name) {
    setTouched((c) => ({ ...c, [name]: true }));
    setErrors((c) => ({ ...c, [name]: validateField(name, values[name], values) }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validateForm(values, REGISTER_FIELDS);
    setErrors(nextErrors);
    setTouched(Object.fromEntries(REGISTER_FIELDS.map((f) => [f, true])));
    if (Object.keys(nextErrors).length > 0) return;

    try {
      await register(values);
      toast.success(t('auth.registered'));
      navigate(redirectTo, { replace: true });
    } catch (error) {
      toast.error(error?.message || t('auth.registerFailed'));
      if (error?.details?.email) setErrors((c) => ({ ...c, email: error.message }));
    }
  }

  const passwordToggle = (
    <button
      type="button"
      onClick={() => setShowPassword((v) => !v)}
      aria-label={showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
      className="flex h-8 w-8 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-ink-100"
    >
      {showPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
    </button>
  );

  return (
    <div className="container-page flex justify-center py-10 lg:py-16">
      <div className="w-full max-w-md">
        <div className="rounded-card border border-ink-200 bg-surface p-6 sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">{t('auth.register')}</h1>
          <p className="mt-1.5 text-sm text-ink-600">
            {t('auth.registerIntro')}
          </p>

          <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label={t('fields.firstName')}
                required
                autoComplete="given-name"
                value={values.firstName}
                error={touched.firstName ? errors.firstName : ''}
                onChange={(e) => handleChange('firstName', e.target.value)}
                onBlur={() => handleBlur('firstName')}
              />
              <Input
                label={t('fields.lastName')}
                required
                autoComplete="family-name"
                value={values.lastName}
                error={touched.lastName ? errors.lastName : ''}
                onChange={(e) => handleChange('lastName', e.target.value)}
                onBlur={() => handleBlur('lastName')}
              />
            </div>

            <Input
              label={t('fields.email')}
              type="email"
              required
              leftIcon={Mail}
              placeholder="you@example.com"
              autoComplete="email"
              value={values.email}
              error={touched.email ? errors.email : ''}
              onChange={(e) => handleChange('email', e.target.value)}
              onBlur={() => handleBlur('email')}
            />

            <Input
              label={t('fields.password')}
              type={showPassword ? 'text' : 'password'}
              required
              autoComplete="new-password"
              hint={t('auth.minChars', { count: MIN_PASSWORD_LENGTH })}
              value={values.password}
              error={touched.password ? errors.password : ''}
              onChange={(e) => handleChange('password', e.target.value)}
              onBlur={() => handleBlur('password')}
              rightSlot={passwordToggle}
            />

            <Input
              label={t('fields.repeatPassword')}
              type={showPassword ? 'text' : 'password'}
              required
              autoComplete="new-password"
              value={values.confirmPassword}
              error={touched.confirmPassword ? errors.confirmPassword : ''}
              onChange={(e) => handleChange('confirmPassword', e.target.value)}
              onBlur={() => handleBlur('confirmPassword')}
            />

            <Button type="submit" size="lg" fullWidth loading={pending}>
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              {t('auth.createAccount')}
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-ink-600">
            {t('auth.haveAccount')}{' '}
            <Link
              to={`/login?${QUERY_KEYS.redirect}=${encodeURIComponent(redirectTo)}`}
              className="font-semibold text-primary-700 underline-offset-4 hover:underline"
            >
              {t('nav.login')}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
