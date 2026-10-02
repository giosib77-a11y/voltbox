import { Link } from 'react-router';
import { Clock, Mail, MapPin, Phone, Zap } from 'lucide-react';
import { CONTACT, INFO_PAGES, SITE_NAME } from '../../constants/index.js';
import { useDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { formatPrice } from '../../utils/format.js';
import { rootCategories } from '../../utils/categoryTree.js';
import { t } from '../../i18n/index.js';

/** საიტის ქვედა კოლონტიტული. */

const INFO_LINKS = [INFO_PAGES.delivery, INFO_PAGES.returns, INFO_PAGES.privacy, INFO_PAGES.faq];

export default function Footer({ categories = [] }) {
  const year = new Date().getFullYear();
  const { rules } = useDeliveryRules();

  return (
    <footer className="mt-auto border-t border-ink-200 bg-surface">
      <div className="container-page grid gap-8 py-10 sm:grid-cols-2 lg:grid-cols-4 lg:py-12">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-control bg-primary-600 text-white">
              <Zap className="h-5 w-5" fill="currentColor" aria-hidden="true" />
            </span>
            <span className="text-lg font-bold tracking-tight text-ink-900">{SITE_NAME}</span>
          </div>
          <p className="mt-3 max-w-xs text-sm leading-relaxed text-ink-600">{t('site.description')}</p>
          {rules && (
            <p className="mt-4 rounded-control bg-primary-50 px-3 py-2 text-xs font-medium text-primary-800">
              {t('footer.freeDelivery', { price: formatPrice(rules.freeFrom) })}
            </p>
          )}
        </div>

        <nav aria-label={t('footer.categoriesNav')}>
          <h2 className="text-sm font-bold text-ink-900">{t('footer.categories')}</h2>
          <ul className="mt-3 space-y-2">
            {rootCategories(categories).map((category) => (
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

        <nav aria-label={t('footer.info')}>
          <h2 className="text-sm font-bold text-ink-900">{t('footer.info')}</h2>
          <ul className="mt-3 space-y-2">
            {INFO_LINKS.map((page) => (
              <li key={page.path}>
                <Link
                  to={page.path}
                  className="text-sm text-ink-600 transition-colors hover:text-primary-700"
                >
                  {t(page.titleKey)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div>
          <h2 className="text-sm font-bold text-ink-900">{t('footer.contact')}</h2>
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
              {t('contact.address')}
            </li>
            <li className="flex items-start gap-2">
              <Clock className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" aria-hidden="true" />
              {t('contact.workHours')}
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-ink-100">
        <div className="container-page flex flex-col items-center justify-between gap-2 py-5 text-xs text-ink-500 sm:flex-row">
          <p>
            © {year} {SITE_NAME}. {t('footer.rights')}
          </p>
          <p>{t('footer.demo')}</p>
        </div>
      </div>
    </footer>
  );
}
