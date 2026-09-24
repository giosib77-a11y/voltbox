import { Link } from 'react-router';
import { Zap } from 'lucide-react';
import { SITE_NAME, SITE_TAGLINE } from '../../constants/index.js';

/** საიტის ლოგო — ყოველთვის მთავარ გვერდზე მიმავალი ბმული. */
export default function Logo({ compact = false, className = '' }) {
  return (
    <Link
      to="/"
      className={`flex shrink-0 items-center gap-2.5 rounded-control ${className}`}
      aria-label={`${SITE_NAME} — მთავარი გვერდი`}
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-control bg-gradient-to-br from-primary-400 to-primary-600 text-white shadow-[0_0_18px_-4px] shadow-primary-600/70 ring-1 ring-inset ring-white/15">
        <Zap className="h-5 w-5" fill="currentColor" aria-hidden="true" />
      </span>
      <span className="flex flex-col leading-none">
        <span className="text-lg font-bold tracking-tight text-fg">{SITE_NAME}</span>
        {!compact && (
          <span className="mt-0.5 hidden text-2xs text-fg-muted lg:block">{SITE_TAGLINE}</span>
        )}
      </span>
    </Link>
  );
}
