import { Clock, Mail, MapPin, Phone } from 'lucide-react';
import { CONTACT } from '../../constants/index.js';
import { TEXT_LINK_CLASS } from './InfoPage.jsx';

/**
 * მაღაზიის კონტაქტი საინფორმაციო გვერდებზე — იმავე `CONTACT`-იდან, რასაც
 * ფუტერი აჩვენებს, რომ ნომრის შეცვლა ყველგან ერთად შეიცვალოს.
 */

/** წინადადების შიგნით: ტელეფონი ან ელფოსტა. */
export function ContactInline() {
  return (
    <>
      <a href={CONTACT.phoneHref} className={`whitespace-nowrap ${TEXT_LINK_CLASS}`}>
        {CONTACT.phone}
      </a>{' '}
      ან{' '}
      <a href={`mailto:${CONTACT.email}`} className={TEXT_LINK_CLASS}>
        {CONTACT.email}
      </a>
    </>
  );
}

/** ცალკე ბლოკად: ტელეფონი, ელფოსტა, მისამართი, სამუშაო საათები. */
export function ContactList() {
  return (
    <ul className="space-y-2.5">
      <li className="flex items-center gap-2.5">
        <Phone className="h-4 w-4 shrink-0 text-ink-400" aria-hidden="true" />
        <a href={CONTACT.phoneHref} className={TEXT_LINK_CLASS}>
          {CONTACT.phone}
        </a>
      </li>
      <li className="flex items-center gap-2.5">
        <Mail className="h-4 w-4 shrink-0 text-ink-400" aria-hidden="true" />
        <a href={`mailto:${CONTACT.email}`} className={TEXT_LINK_CLASS}>
          {CONTACT.email}
        </a>
      </li>
      <li className="flex items-start gap-2.5">
        <MapPin className="mt-1 h-4 w-4 shrink-0 text-ink-400" aria-hidden="true" />
        {CONTACT.address}
      </li>
      <li className="flex items-start gap-2.5">
        <Clock className="mt-1 h-4 w-4 shrink-0 text-ink-400" aria-hidden="true" />
        {CONTACT.workHours}
      </li>
    </ul>
  );
}
