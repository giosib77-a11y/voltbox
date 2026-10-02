import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { Eye, EyeOff, LogIn, Mail } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import Input from '../components/common/Input.jsx';
import { useAuth } from '../hooks/useAuth.js';
import { useToast } from '../hooks/useToast.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { useEmailEnabled } from '../hooks/useEmailEnabled.js';
import { LOGIN_FIELDS, validateField, validateForm } from '../utils/validate.js';
import { QUERY_KEYS, SITE_NAME } from '../constants/index.js';
import { getSafeRedirect } from '../utils/redirect.js';
import { t } from '../i18n/index.js';
import Rich from '../i18n/Rich.jsx';

// MOCK ONLY — replace with real auth API.
export default function Login() {
  useDocumentTitle(t('nav.login'));

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Untrusted: the parameter arrives from a link anyone can write, and an
  // unchecked value turns this page into an open redirect - a login form on
  // the real site that lands the user somewhere else afterwards.
  const redirectTo = getSafeRedirect(
    searchParams.get(QUERY_KEYS.redirect),
    '/account/orders',
  );

  const { login, pending } = useAuth();
  const toast = useToast();
  // A link that sends nothing is worse than no link: while the shop cannot
  // send email, there is no way to recover a password here at all.
  const canResetPassword = useEmailEnabled();

  const [values, setValues] = useState({ email: '', password: '' });
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [showPassword, setShowPassword] = useState(false);

  function handleChange(name, value) {
    setValues((current) => ({ ...current, [name]: value }));
    if (touched[name]) setErrors((c) => ({ ...c, [name]: validateField(name, value, values) }));
  }

  function handleBlur(name) {
    setTouched((c) => ({ ...c, [name]: true }));
    setErrors((c) => ({ ...c, [name]: validateField(name, values[name], values) }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validateForm(values, LOGIN_FIELDS);
    setErrors(nextErrors);
    setTouched({ email: true, password: true });
    if (Object.keys(nextErrors).length > 0) return;

    try {
      await login(values);
      toast.success(t('auth.welcomeBack'));
      navigate(redirectTo, { replace: true });
    } catch (error) {
      toast.error(error?.message || t('auth.loginFailed'));
      setErrors({ password: error?.message || t('apiErrors.INVALID_CREDENTIALS') });
    }
  }

  return (
    <div className="container-page flex justify-center py-10 lg:py-16">
      <div className="w-full max-w-md">
        <div className="rounded-card border border-ink-200 bg-surface p-6 sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">{t('nav.login')}</h1>
          <p className="mt-1.5 text-sm text-ink-600">
            {t('auth.loginIntro')}
          </p>

          <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
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
              autoComplete="current-password"
              value={values.password}
              error={touched.password ? errors.password : ''}
              onChange={(e) => handleChange('password', e.target.value)}
              onBlur={() => handleBlur('password')}
              rightSlot={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
                  className="flex h-8 w-8 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-ink-100"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              }
            />

            {canResetPassword && (
              <p className="-mt-1 text-right text-sm">
                <Link
                  to="/forgot-password"
                  className="font-medium text-primary-700 underline-offset-4 hover:underline"
                >
                  {t('auth.forgot')}
                </Link>
              </p>
            )}

            <Button type="submit" size="lg" fullWidth loading={pending}>
              <LogIn className="h-4 w-4" aria-hidden="true" />
              {t('nav.login')}
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-ink-600">
            {t('auth.noAccount')}{' '}
            <Link
              to={`/register${redirectTo ? `?${QUERY_KEYS.redirect}=${encodeURIComponent(redirectTo)}` : ''}`}
              className="font-semibold text-primary-700 underline-offset-4 hover:underline"
            >
              {t('auth.register')}
            </Link>
          </p>
        </div>

        <p className="mt-4 rounded-control bg-ink-100 px-4 py-3 text-center text-xs leading-relaxed text-ink-600">
          <Rich k="auth.demoNote" values={{ label: <strong>{t('auth.demoLabel')}</strong>, site: SITE_NAME }} />
        </p>
      </div>
    </div>
  );
}
