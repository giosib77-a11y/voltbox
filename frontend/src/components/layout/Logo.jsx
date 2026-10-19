import { Link } from 'react-router';
import { SITE_NAME } from '../../constants/index.js';
import { t } from '../../i18n/index.js';

/**
 * The brand mark (DESIGN.md §7): a double rhombus with a bolt. The only copy
 * of the path — footer, mobile menu and hero import it. Colour comes from
 * `currentColor`, so the caller sets `text-primary-500` (the default here).
 */
export function LogoMark({ size = 46, className = 'text-primary-500' }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 70 70"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={`shrink-0 ${className}`}
    >
      <path d="M35 3 67 35 35 67 3 35z" />
      <path d="M35 10 60 35 35 60 10 35z" strokeOpacity=".45" />
      <path d="M38 21l-11 16h8l-3 12 11-16h-8l3-12z" />
    </svg>
  );
}

/** საიტის ლოგო — ყოველთვის მთავარ გვერდზე მიმავალი ბმული. */
export default function Logo({ compact = false, className = '' }) {
  return (
    <Link
      to="/"
      className={`flex shrink-0 items-center gap-2.5 rounded-control md:gap-3.5 ${className}`}
      aria-label={t('layout.logoLabel', { site: SITE_NAME })}
    >
      <LogoMark size={46} className="h-[34px] w-[34px] text-primary-500 md:h-[46px] md:w-[46px]" />
      <span className="flex flex-col">
        <span className="-mr-[0.26em] font-display text-[17px] font-semibold uppercase leading-none tracking-[0.26em] text-fg md:-mr-[0.32em] md:text-[22px] md:tracking-[0.32em]">
          {SITE_NAME}
        </span>
        {!compact && (
          <span className="mt-1 hidden text-2xs leading-none text-fg-muted lg:block">
            {t('site.tagline')}
          </span>
        )}
      </span>
    </Link>
  );
}
