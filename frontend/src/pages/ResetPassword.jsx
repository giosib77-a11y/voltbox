import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { KeyRound } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import Input from '../components/common/Input.jsx';
import { useToast } from '../hooks/useToast.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { useEmailEnabled } from '../hooks/useEmailEnabled.js';
import * as api from '../services/api.js';
import {
  MIN_PASSWORD_LENGTH,
  RESET_PASSWORD_FIELDS,
  validateField,
  validateForm,
} from '../utils/validate.js';

const EMPTY = { newPassword: '', confirmPassword: '' };
const LINK_CLASS = 'font-semibold text-primary-700 underline-offset-4 hover:underline';

/** The token from `#token=…`, or null. */
function tokenFrom(hash) {
  const token = new URLSearchParams(String(hash || '').replace(/^#/, '')).get('token');
  return token?.trim() || null;
}

/**
 * ახალი პაროლი წერილის ბმულით.
 *
 * ტოკენი ბმულის fragment-შია (`#token=…`) და არა query-ში: fragment-ს ბრაუზერი
 * სერვერს არასდროს უგზავნის — არც გვერდის მომსახურე host-ს, არც Referer-ში,
 * არც crash-რეპორტში (`reportError` მხოლოდ path-სა და query-ს აგზავნის).
 * გვერდი მას ერთხელ კითხულობს და მისამართის ზოლიდან მაშინვე შლის, რომ ეკრანზე
 * და ისტორიაში აღარ ეწეროს. გადატვირთვის შემდეგ ბმული წერილიდან ხელახლა
 * უნდა გაიხსნას — ის გამოყენებამდე ისევ მოქმედია.
 *
 * ახალი პაროლი რეგისტრაციის წესებს მისდევს; წარმატების შემდეგ სერვერი
 * ანგარიშის ყველა სესიას ხურავს, ამიტომ გვერდი შესვლაზე გადადის.
 */
export default function ResetPassword() {
  useDocumentTitle('ახალი პაროლი');

  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const emailEnabled = useEmailEnabled();

  const [token] = useState(() => tokenFrom(location.hash));
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [saving, setSaving] = useState(false);
  const [linkDead, setLinkDead] = useState(false);

  useEffect(() => {
    if (location.hash) {
      navigate({ pathname: location.pathname, search: location.search }, { replace: true });
    }
  }, [location.hash, location.pathname, location.search, navigate]);

  function handleChange(name, value) {
    const next = { ...values, [name]: value };
    setValues(next);
    if (touched[name]) setErrors((c) => ({ ...c, [name]: validateField(name, value, next) }));
    if (name === 'newPassword' && touched.confirmPassword) {
      setErrors((c) => ({
        ...c,
        confirmPassword: validateField('confirmPassword', next.confirmPassword, next),
      }));
    }
  }

  function handleBlur(name) {
    setTouched((c) => ({ ...c, [name]: true }));
    setErrors((c) => ({ ...c, [name]: validateField(name, values[name], values) }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validateForm(values, RESET_PASSWORD_FIELDS);
    setErrors(nextErrors);
    setTouched(Object.fromEntries(RESET_PASSWORD_FIELDS.map((f) => [f, true])));
    if (Object.keys(nextErrors).length > 0) return;

    setSaving(true);
    try {
      await api.resetPassword({ token, newPassword: values.newPassword });
      toast.success('პაროლი შეიცვალა. შედით ახალი პაროლით.');
      navigate('/login', { replace: true });
    } catch (error) {
      if (error?.details?.code === 'INVALID_RESET_TOKEN') {
        setLinkDead(true);
        return;
      }
      // The one rule the server checks and this page does not: a password
      // from the list of the most common ones.
      const fields = error?.details?.details;
      if (Array.isArray(fields) && fields.some((f) => f?.field === 'newPassword')) {
        setErrors({ newPassword: 'ეს პაროლი ძალიან მარტივია — აირჩიეთ სხვა.' });
        return;
      }
      toast.error(error?.message || 'პაროლი ვერ შეიცვალა');
    } finally {
      setSaving(false);
    }
  }

  let body;
  if (!token || linkDead) {
    body = (
      <div role="alert" className="mt-4 space-y-3 text-sm text-ink-700">
        <p>
          {linkDead
            ? 'ბმული არასწორია ან მისი ვადა ამოიწურა. თუ აღდგენა რამდენჯერმე მოითხოვეთ, იმუშავებს მხოლოდ ბოლო წერილის ბმული.'
            : 'ბმული არასრულია. გახსენით ის წერილიდან ხელახლა.'}
        </p>
        {emailEnabled && (
          <p>
            <Link to="/forgot-password" className={LINK_CLASS}>
              ახალი ბმულის მოთხოვნა
            </Link>
          </p>
        )}
      </div>
    );
  } else {
    body = (
      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
        <Input
          label="ახალი პაროლი"
          type="password"
          required
          autoComplete="new-password"
          hint={`მინიმუმ ${MIN_PASSWORD_LENGTH} სიმბოლო`}
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
        <Button type="submit" size="lg" fullWidth loading={saving}>
          <KeyRound className="h-4 w-4" aria-hidden="true" />
          პაროლის შეცვლა
        </Button>
      </form>
    );
  }

  return (
    <div className="container-page flex justify-center py-10 lg:py-16">
      <div className="w-full max-w-md">
        <div className="rounded-card border border-ink-200 bg-surface p-6 sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">ახალი პაროლი</h1>
          <p className="mt-1.5 text-sm text-ink-600">
            პაროლის შეცვლის შემდეგ ანგარიშიდან ყველა მოწყობილობაზე გამოხვალთ.
          </p>

          {body}

          <p className="mt-5 text-center text-sm text-ink-600">
            <Link to="/login" className={LINK_CLASS}>
              შესვლის გვერდზე დაბრუნება
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
