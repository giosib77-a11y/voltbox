import { Link } from 'react-router';
import { Clock, Mail, MapPin, Phone } from 'lucide-react';
import { LogoMark } from './Logo.jsx';
import { CONTACT, INFO_PAGES, SITE_NAME } from '../../constants/index.js';
import { useDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { formatPrice } from '../../utils/format.js';
import { rootCategories } from '../../utils/categoryTree.js';
import { t } from '../../i18n/index.js';

/** საიტის ქვედა კოლონტიტული. */

const INFO_LINKS = [INFO_PAGES.delivery, INFO_PAGES.returns, INFO_PAGES.privacy, INFO_PAGES.faq];

const HEADING = 'font-serif text-[15px] font-medium leading-snug tracking-[0.06em] text-primary-700';
const LINK = 'text-fg-muted transition-colors hover:text-primary-700';

export default function Footer({ categories = [] }) {
  const year = new Date().getFullYear();
  const { rules } = useDeliveryRules();

  return (
    <footer className="mt-auto border-t border-line bg-footer">
      <div className="container-page grid gap-10 py-12 sm:grid-cols-2 lg:grid-cols-4 lg:pb-12 lg:pt-[72px]">
        <div className="flex flex-col gap-[18px]">
          {/* DESIGN.md §7: mark 50px / 40px, wordmark 22px 0.32em / 20px 0.28em */}
          <div className="flex items-center gap-3.5">
            <LogoMark size={50} className="h-10 w-10 text-primary-500 sm:h-[50px] sm:w-[50px]" />
            <span className="font-display text-xl font-semibold uppercase leading-none tracking-[0.28em] text-fg sm:text-[22px] sm:tracking-[0.32em]">
              {SITE_NAME}
            </span>
          </div>
          <p className="max-w-xs text-[13px] leading-[1.85] text-fg-muted">{t('site.description')}</p>
          {rules && (
            <p className="self-start border border-primary-500 px-3.5 py-2 text-xs tracking-[0.06em] text-primary-700">
              {t('footer.freeDelivery', { price: formatPrice(rules.freeFrom) })}
            </p>
          )}
        </div>

        <nav aria-label={t('footer.categoriesNav')}>
          <h2 className={HEADING}>{t('footer.categories')}</h2>
          <ul className="mt-4 space-y-3 text-sm">
            {rootCategories(categories).map((category) => (
              <li key={category.id}>
                <Link to={`/category/${category.slug}`} className={LINK}>
                  {category.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <nav aria-label={t('footer.info')}>
          <h2 className={HEADING}>{t('footer.info')}</h2>
          <ul className="mt-4 space-y-3 text-sm">
            {INFO_LINKS.map((page) => (
              <li key={page.path}>
                <Link to={page.path} className={LINK}>
                  {t(page.titleKey)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div>
          <h2 className={HEADING}>{t('footer.contact')}</h2>
          <ul className="mt-4 space-y-3.5 text-[13px] text-fg-muted">
            <li>
              <a href={CONTACT.phoneHref} className={`flex items-center gap-3 ${LINK}`}>
                <Phone className="h-4 w-4 shrink-0 text-primary-500" aria-hidden="true" />
                {CONTACT.phone}
              </a>
            </li>
            <li>
              <a href={`mailto:${CONTACT.email}`} className={`flex items-center gap-3 ${LINK}`}>
                <Mail className="h-4 w-4 shrink-0 text-primary-500" aria-hidden="true" />
                {CONTACT.email}
              </a>
            </li>
            <li className="flex items-start gap-3">
              <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary-500" aria-hidden="true" />
              {t('contact.address')}
            </li>
            <li className="flex items-start gap-3">
              <Clock className="mt-0.5 h-4 w-4 shrink-0 text-primary-500" aria-hidden="true" />
              {t('contact.workHours')}
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-line">
        <div className="container-page flex flex-col items-center justify-between gap-2 py-5 text-xs tracking-[0.04em] text-fg-muted sm:flex-row">
          <p>
            © {year} {SITE_NAME}. {t('footer.rights')}
          </p>
          {/* Substituted at build time, so an http build ships neither the branch nor the text. */}
          {import.meta.env?.VITE_API_MODE !== 'http' && <p>{t('footer.demo')}</p>}
        </div>
      </div>
    </footer>
  );
}
