import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Eye, EyeOff, LogIn, Mail } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import Input from '../components/common/Input.jsx';
import { useAuth } from '../hooks/useAuth.js';
import { useToast } from '../hooks/useToast.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { LOGIN_FIELDS, validateField, validateForm } from '../utils/validate.js';
import { QUERY_KEYS, SITE_NAME } from '../constants/index.js';

// MOCK ONLY — replace with real auth API.
export default function Login() {
  useDocumentTitle('შესვლა');

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTo = searchParams.get(QUERY_KEYS.redirect) || '/account/orders';

  const { login, pending } = useAuth();
  const toast = useToast();

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
      toast.success('კეთილი იყოს თქვენი დაბრუნება!');
      navigate(redirectTo, { replace: true });
    } catch (error) {
      toast.error(error?.message || 'შესვლა ვერ მოხერხდა');
      setErrors({ password: error?.message || 'ელ. ფოსტა ან პაროლი არასწორია' });
    }
  }

  return (
    <div className="container-page flex justify-center py-10 lg:py-16">
      <div className="w-full max-w-md">
        <div className="rounded-card border border-ink-200 bg-white p-6 sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">შესვლა</h1>
          <p className="mt-1.5 text-sm text-ink-600">
            შედით ანგარიშში შეკვეთების ისტორიისა და მისამართების სანახავად.
          </p>

          <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
            <Input
              label="ელ. ფოსტა"
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
              label="პაროლი"
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
                  aria-label={showPassword ? 'პაროლის დამალვა' : 'პაროლის ჩვენება'}
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

            <Button type="submit" size="lg" fullWidth loading={pending}>
              <LogIn className="h-4 w-4" aria-hidden="true" />
              შესვლა
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-ink-600">
            არ გაქვთ ანგარიში?{' '}
            <Link
              to={`/register${redirectTo ? `?${QUERY_KEYS.redirect}=${encodeURIComponent(redirectTo)}` : ''}`}
              className="font-semibold text-primary-700 underline-offset-4 hover:underline"
            >
              რეგისტრაცია
            </Link>
          </p>
        </div>

        <p className="mt-4 rounded-control bg-ink-100 px-4 py-3 text-center text-xs leading-relaxed text-ink-600">
          <strong>დემო რეჟიმი:</strong> {SITE_NAME}-ის ავტორიზაცია mock-ია და მონაცემები ინახება
          მხოლოდ ამ ბრაუზერში. შეკვეთისთვის ანგარიში საჭირო არ არის.
        </p>
      </div>
    </div>
  );
}
