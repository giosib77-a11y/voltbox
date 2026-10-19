import { useLocation } from 'react-router';
import { Globe } from 'lucide-react';
import { currentLanguage, localizedPath, t } from '../../i18n/index.js';

/**
 * The page in the other language - a link, not a button.
 *
 * Shows the language the page is in; its name says which one it switches to,
 * as the theme toggle's does, because that is what activating it does. Keeps
 * the page: the router's path (no language in it), the query and the hash, put
 * under the other language's prefix.
 *
 * A plain <a>, so following it loads the page again in the other language -
 * see i18n/index.js for why the language never changes under a running page.
 * As a real link it is also one a crawler can follow.
 */
export default function LanguageSwitch({ className = '', onNavigate }) {
  const location = useLocation();
  const language = currentLanguage();
  const other = language === 'en' ? 'ka' : 'en';
  const href = `${localizedPath(location.pathname, other)}${location.search}${location.hash}`;
  const label = t('language.switchTo');

  return (
    <a
      href={href}
      hrefLang={other}
      onClick={onNavigate}
      aria-label={label}
      title={label}
      className={`flex h-11 items-center gap-2 rounded-control px-3 text-sm text-fg transition-colors hover:bg-ink-100 active:bg-ink-200 md:h-[46px] ${className}`}
    >
      <Globe className="h-[18px] w-[18px]" aria-hidden="true" />
      <span>{t('language.current')}</span>
    </a>
  );
}
