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
    <div className="container-page py-5 lg:py-7">
      <Breadcrumbs items={[{ label: title }]} className="mb-4" />
      <div className="max-w-[720px]">
        <h1 className="font-serif text-[28px] font-light leading-tight text-ink-900 lg:text-4xl">
          {title}
        </h1>
        <div className="mt-6 space-y-8 text-sm leading-[1.8] text-ink-700 lg:text-[15px] lg:leading-[1.85]">
          {children}
        </div>
      </div>
    </div>
  );
}

export function InfoSection({ title, children }) {
  return (
    <section className="space-y-3">
      <h2 className="font-serif text-[22px] font-light leading-snug text-ink-900 lg:text-2xl">
        {title}
      </h2>
      {children}
    </section>
  );
}

/** ბმული ტექსტის შიგნით — ხაზგასმული, რომ ფერის გარეშეც ჩანდეს. */
export const TEXT_LINK_CLASS =
  'rounded-sm font-semibold text-primary-700 underline underline-offset-4 hover:text-primary-800';

/** A bulleted list whose marker is the shop's small diamond (DESIGN.md §9.1). */
export const DIAMOND_LIST_CLASS =
  'space-y-1.5 [&>li]:relative [&>li]:pl-5 [&>li]:before:absolute [&>li]:before:left-0.5 [&>li]:before:top-[0.7em] [&>li]:before:h-1 [&>li]:before:w-1 [&>li]:before:rotate-45 [&>li]:before:bg-primary-500';
