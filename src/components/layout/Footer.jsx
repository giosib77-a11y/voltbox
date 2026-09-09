import { Link } from 'react-router-dom';
import { Clock, Mail, MapPin, Phone, Zap } from 'lucide-react';
import { CONTACT, SHIPPING, SITE_DESCRIPTION, SITE_NAME } from '../../constants/index.js';
import { formatPrice } from '../../utils/format.js';

/** საიტის ქვედა კოლონტიტული. */

const INFO_LINKS = [
  { label: 'მიწოდების პირობები', to: '/category/phones' },
  { label: 'დაბრუნება და გარანტია', to: '/category/accessories' },
  { label: 'კონფიდენციალურობა', to: '/' },
  { label: 'ხშირად დასმული კითხვები', to: '/' },
];

export default function Footer({ categories = [] }) {
  const year = new Date().getFullYear();

  return (
    <footer className="mt-auto border-t border-ink-200 bg-white">
      <div className="container-page grid gap-8 py-10 sm:grid-cols-2 lg:grid-cols-4 lg:py-12">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-control bg-primary-600 text-white">
              <Zap className="h-5 w-5" fill="currentColor" aria-hidden="true" />
            </span>
            <span className="text-lg font-bold tracking-tight text-ink-900">{SITE_NAME}</span>
          </div>
          <p className="mt-3 max-w-xs text-sm leading-relaxed text-ink-600">{SITE_DESCRIPTION}</p>
          <p className="mt-4 rounded-control bg-primary-50 px-3 py-2 text-xs font-medium text-primary-800">
            უფასო მიწოდება {formatPrice(SHIPPING.freeThreshold)}-დან
          </p>
        </div>

        <nav aria-label="კატეგორიები (ქვედა მენიუ)">
          <h2 className="text-sm font-bold text-ink-900">კატეგორიები</h2>
          <ul className="mt-3 space-y-2">
            {categories.map((category) => (
              <li key={category.id}>
                <Link
                  to={`/category/${category.slug}`}
                  className="text-sm text-ink-600 transition-colors hover:text-primary-700"
                >
                  {category.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <nav aria-label="ინფორმაცია">
          <h2 className="text-sm font-bold text-ink-900">ინფორმაცია</h2>
          <ul className="mt-3 space-y-2">
            {INFO_LINKS.map((link) => (
              <li key={link.label}>
                <Link
                  to={link.to}
                  className="text-sm text-ink-600 transition-colors hover:text-primary-700"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div>
          <h2 className="text-sm font-bold text-ink-900">კონტაქტი</h2>
          <ul className="mt-3 space-y-2.5 text-sm text-ink-600">
            <li>
              <a href={CONTACT.phoneHref} className="flex items-center gap-2 hover:text-primary-700">
                <Phone className="h-4 w-4 shrink-0 text-ink-400" aria-hidden="true" />
                {CONTACT.phone}
              </a>
            </li>
            <li>
              <a href={`mailto:${CONTACT.email}`} className="flex items-center gap-2 hover:text-primary-700">
                <Mail className="h-4 w-4 shrink-0 text-ink-400" aria-hidden="true" />
                {CONTACT.email}
              </a>
            </li>
            <li className="flex items-start gap-2">
              <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" aria-hidden="true" />
              {CONTACT.address}
            </li>
            <li className="flex items-start gap-2">
              <Clock className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" aria-hidden="true" />
              {CONTACT.workHours}
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-ink-100">
        <div className="container-page flex flex-col items-center justify-between gap-2 py-5 text-xs text-ink-500 sm:flex-row">
          <p>
            © {year} {SITE_NAME}. ყველა უფლება დაცულია.
          </p>
          <p>დემო პროექტი — მონაცემები mock წყაროდან.</p>
        </div>
      </div>
    </footer>
  );
}
