import { useState } from 'react';
import { Link } from 'react-router';
import { Mail, Send } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import Input from '../components/common/Input.jsx';
import { Skeleton } from '../components/common/Skeleton.jsx';
import { useToast } from '../hooks/useToast.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { useDeliveryRules } from '../hooks/useDeliveryRules.js';
import { useEmailEnabled } from '../hooks/useEmailEnabled.js';
import * as api from '../services/api.js';
import { validateField } from '../utils/validate.js';
import { CONTACT } from '../constants/index.js';

const LINK_CLASS = 'font-semibold text-primary-700 underline-offset-4 hover:underline';

/**
 * „დაგავიწყდათ პაროლი?" — მისამართი, რომელზეც აღდგენის ბმული წავა.
 *
 * პასუხი ყოველთვის ერთია, ანგარიში არსებობს თუ არა: სერვერი ორივეს ერთნაირად
 * პასუხობს და გვერდიც ერთსა და იმავეს წერს. სხვაგვარად ეს ფორმა ნებისმიერს
 * ეტყოდა, ვინ არის დარეგისტრირებული.
 *
 * სანამ მაღაზიას წერილის გაგზავნა არ შეუძლია, ფორმა არ ჩანს — შესვლის
 * გვერდი აქ ბმულს მაშინ არც აჩვენებს, ასე რომ აქ მხოლოდ მისამართის ხელით
 * აკრეფით მოხვდებით.
 */
export default function ForgotPassword() {
  useDocumentTitle('პაროლის აღდგენა');

  const { loading } = useDeliveryRules();
  const emailEnabled = useEmailEnabled();
  const toast = useToast();

  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [sentTo, setSentTo] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    const message = validateField('email', email);
    setTouched(true);
    setError(message);
    if (message) return;

    setSending(true);
    try {
      const address = email.trim();
      await api.requestPasswordReset({ email: address });
      setSentTo(address);
    } catch (failure) {
      toast.error(failure?.message || 'მოთხოვნა ვერ გაიგზავნა');
    } finally {
      setSending(false);
    }
  }

  let body;
  if (loading) {
    body = <Skeleton className="mt-6 h-24 w-full" />;
  } else if (!emailEnabled) {
    body = (
      <p className="mt-4 text-sm text-ink-700">
        პაროლის აღდგენა ამჟამად მიუწვდომელია. დაგვიკავშირდით ტელეფონით:{' '}
        <a href={CONTACT.phoneHref} className={LINK_CLASS}>
          {CONTACT.phone}
        </a>
        .
      </p>
    );
  } else if (sentTo) {
    body = (
      <div role="status" className="mt-4 space-y-2 text-sm text-ink-700">
        <p>
          თუ <strong className="text-ink-900">{sentTo}</strong> ანგარიშს ეკუთვნის, მასზე
          პაროლის აღდგენის ბმული გაიგზავნა.
        </p>
        <p>ბმული მხოლოდ ერთხელ იმუშავებს. წერილი თუ არ ჩანს, სპამის საქაღალდეც შეამოწმეთ.</p>
      </div>
    );
  } else {
    body = (
      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
        <Input
          label="ელ. ფოსტა"
          type="email"
          required
          leftIcon={Mail}
          placeholder="you@example.com"
          autoComplete="email"
          value={email}
          error={touched ? error : ''}
          onChange={(e) => {
            setEmail(e.target.value);
            if (touched) setError(validateField('email', e.target.value));
          }}
          onBlur={() => {
            setTouched(true);
            setError(validateField('email', email));
          }}
        />
        <Button type="submit" size="lg" fullWidth loading={sending}>
          <Send className="h-4 w-4" aria-hidden="true" />
          ბმულის გაგზავნა
        </Button>
      </form>
    );
  }

  return (
    <div className="container-page flex justify-center py-10 lg:py-16">
      <div className="w-full max-w-md">
        <div className="rounded-card border border-ink-200 bg-surface p-6 sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">პაროლის აღდგენა</h1>
          <p className="mt-1.5 text-sm text-ink-600">
            შეიყვანეთ ანგარიშის ელ. ფოსტა — ახალი პაროლის დასაყენებელ ბმულს გამოგიგზავნით.
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
