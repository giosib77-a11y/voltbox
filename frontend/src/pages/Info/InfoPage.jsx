import Breadcrumbs from '../../components/common/Breadcrumbs.jsx';
import { useDocumentTitle } from '../../hooks/useDocumentTitle.js';
import { usePageMeta } from '../../hooks/usePageMeta.js';

/**
 * ფუტერის საინფორმაციო გვერდების საერთო ჩარჩო — ბილიკი, სათაური, meta.
 *
 * `page` არის `INFO_PAGES`-ის ჩანაწერი: სათაური იგივეა, რაც ფუტერის ბმულს
 * აწერია, canonical კი — ის მისამართი, რომელზეც მარშრუტი დგას.
 */
export default function InfoPage({ page, description, children }) {
  useDocumentTitle(page.title);
  usePageMeta({ description, canonical: page.path });

  return (
    <div className="container-page max-w-3xl py-8 lg:py-12">
      <Breadcrumbs items={[{ label: page.title }]} className="mb-4" />
      <h1 className="text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">{page.title}</h1>
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
