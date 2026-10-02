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
      className={`flex h-10 items-center gap-1.5 rounded-control px-2.5 text-sm font-semibold text-ink-700 transition-colors hover:bg-ink-100 hover:text-fg ${className}`}
    >
      <Globe className="h-5 w-5" aria-hidden="true" />
      <span>{t('language.current')}</span>
    </a>
  );
}
