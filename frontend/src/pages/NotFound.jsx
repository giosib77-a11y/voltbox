import { Home, Search } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import { LogoMark } from '../components/layout/Logo.jsx';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { t } from '../i18n/index.js';

/** 404 — ყველა უცნობი მარშრუტისთვის. */
export default function NotFound() {
  useDocumentTitle(t('notFound.title'));

  return (
    <div className="container-page flex min-h-[60vh] flex-col items-center justify-center py-14 text-center">
      <LogoMark size={96} className="text-primary-500" />
      <p className="sr-only">404</p>
      <h1 className="mt-6 font-serif text-[28px] font-light leading-tight text-ink-900 lg:text-4xl">
        {t('notFound.title')}
      </h1>
      <p className="mt-2.5 max-w-md text-sm leading-[1.8] text-ink-600">
        {t('notFound.text')}
      </p>

      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <Button to="/" size="lg">
          <Home className="h-4 w-4" aria-hidden="true" />
          {t('notFound.home')}
        </Button>
        <Button to="/search" variant="outline" size="lg">
          <Search className="h-4 w-4" aria-hidden="true" />
          {t('common.search')}
        </Button>
      </div>
    </div>
  );
}
