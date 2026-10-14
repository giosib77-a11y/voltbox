import Breadcrumbs from '../../components/common/Breadcrumbs.jsx';
import { useDocumentTitle } from '../../hooks/useDocumentTitle.js';
import { usePageMeta } from '../../hooks/usePageMeta.js';
import { t } from '../../i18n/index.js';

/**
 * ფუტერის საინფორმაციო გვერდების საერთო ჩარჩო — ბილიკი, სათაური, meta.
 *
 * `page` არის `INFO_PAGES`-ის ჩანაწერი: სათაური იგივეა, რაც ფუტერის ბმულს
 * აწერია, canonical კი — ის მისამართი, რომელზეც მარშრუტი დგას.
 *
 * The whole page - frame and text - is in the page's language, so the text
 * carries no `lang` of its own: it is the document's.
 */
export default function InfoPage({ page, description, children }) {
  const title = t(page.titleKey);
  useDocumentTitle(title);
  usePageMeta({ description, canonical: page.path });

  return (
    <div className="container-page max-w-3xl py-8 lg:py-12">
      <Breadcrumbs items={[{ label: title }]} className="mb-4" />
      <h1 className="text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">{title}</h1>
      <div className="mt-6 space-y-8 text-sm leading-relaxed text-ink-700 sm:text-base">
        {children}
      </div>
    </div>
  );
}

export function InfoSection({ title, children }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold text-ink-900">{title}</h2>
      {children}
    </section>
  );
}

/** ბმული ტექსტის შიგნით — ხაზგასმული, რომ ფერის გარეშეც ჩანდეს. */
export const TEXT_LINK_CLASS =
  'font-semibold text-primary-700 underline underline-offset-4 hover:text-primary-800';
