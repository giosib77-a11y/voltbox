import { Link } from 'react-router';
import { ArrowRight, BadgePercent, Headphones, ShieldCheck, Truck } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import CategoryIcon from '../components/common/CategoryIcon.jsx';
import { LogoMark } from '../components/layout/Logo.jsx';
import CategoryNav from '../components/layout/CategoryNav.jsx';
import ProductCarousel from '../components/product/ProductCarousel.jsx';
import ErrorState from '../components/common/ErrorState.jsx';
import { Skeleton } from '../components/common/Skeleton.jsx';
import { useAsync, useCategories } from '../hooks/useProducts.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import * as api from '../services/api.js';
import { useDeliveryRules } from '../hooks/useDeliveryRules.js';
import { formatItemsCount, formatPrice } from '../utils/format.js';
import { rootCategories } from '../utils/categoryTree.js';
import { t } from '../i18n/index.js';
import Rich from '../i18n/Rich.jsx';

// `title` and `text` are translation keys; the hours are the footer's.
const BENEFITS = [
  // The threshold is filled in from GET /delivery when the card renders; until
  // then a no-break space holds the line, so the card does not jump.
  {
    icon: Truck,
    title: 'home.benefits.freeDelivery',
    text: (rules) =>
      rules ? t('home.benefits.freeDeliveryText', { price: formatPrice(rules.freeFrom) }) : ' ',
  },
  { icon: ShieldCheck, title: 'home.benefits.warranty', text: 'home.benefits.warrantyText' },
  { icon: BadgePercent, title: 'home.benefits.price', text: 'home.benefits.priceText' },
  { icon: Headphones, title: 'home.benefits.advice', text: 'contact.workHours' },
];

export default function Home() {
  useDocumentTitle('');
  const { data, loading, error, reload } = useAsync(() => api.getHomeSections(), []);
  // იგივე მოთხოვნა, რაც header-ისა და footer-ის — useCategories მას ერთხელ აგზავნის
  const { data: categories } = useCategories();

  const sections = data || {};

  return (
    <div className="container-page pb-14 pt-5 lg:pb-[88px] lg:pt-8">
      {/* desktop: კატეგორიების სია hero-ს მარცხნივ, ქვეკატეგორიები მარჯვნივ hero-ს
          თავზე იშლება (z-10 — hero და მის შემდეგ მოსული სექციები ქვემოთ რჩება).
          mobile-ზე სია არ არის — იქ drawer-ია.
          სვეტი თავისი შიგთავსის სიმაღლისაა (self-start) და არა hero-სი: ყოველი
          ახალი კატეგორია მას ერთი ხაზით ზრდის. hero-ზე გრძელი სია hero-ს გასცდება
          და საკუთარ scroll-ს არ იღებს: hover-ით სამართავ მენიუში scroll-ის მიღმა
          კატეგორიები დამალული დარჩებოდა, და ამოსული flyout ხაზს ჩამოშორდებოდა.
          hero ამ დროს stretch-ით სვეტამდე იზრდება, ასე რომ ხვრელი არ რჩება */}
      <div className="md:grid md:grid-cols-[14rem_minmax(0,1fr)] md:gap-7 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="relative z-10 hidden md:block md:self-start">
          <CategoryNav
            categories={categories || []}
            className="rounded-card border border-line bg-surface"
          />
        </aside>
        <Hero categories={categories || []} />
      </div>
      <Benefits />

      <PopularCategories categories={sections.popularCategories || []} loading={loading} />

      {error ? (
        <div className="py-8">
          <ErrorState error={error} onRetry={reload} />
        </div>
      ) : (
        <>
          <ProductCarousel
            title={t('home.newArrivals')}
            products={sections.newArrivals || []}
            loading={loading}
          />
          <ProductCarousel
            title={t('home.discounted')}
            products={sections.discounted || []}
            loading={loading}
          />
          <ProductCarousel
            title={t('home.featured')}
            products={sections.featured || []}
            loading={loading}
          />
          {/* API-ს სავსე მხოლოდ მაშინ, როცა სამივე ზემოთა ცარიელია. ჩატვირთვისას
              skeleton-ს არ ვაჩვენებთ — თორემ მეოთხე ზოლი ყოველ ჯერზე გაქრებოდა */}
          {!loading && (
            <ProductCarousel title={t('home.latest')} products={sections.latest || []} />
          )}
        </>
      )}
    </div>
  );
}

/**
 * The hero's two buttons are the first two top-level categories, in the order
 * the owner sets in the admin. They used to be the slugs `phones` and
 * `headphones` written into this file: the owner deleted Phones, and the main
 * button on the home page led to "category not found". Taken from the list the
 * API returns, a deleted category simply is not there, and the next one moves
 * up. No category, no button; while the list loads, the row keeps its height.
 */
function Hero({ categories }) {
  const [first, second] = rootCategories(categories);
  return (
    <section className="border border-line bg-surface px-5 py-7 md:p-10 lg:p-14 xl:p-16 rounded-card">
      <div className="flex items-center justify-between gap-10">
        <div className="max-w-[520px]">
          <p className="flex items-center gap-3.5 text-xs font-medium tracking-[0.14em] text-primary-700">
            <span aria-hidden="true" className="h-px w-9 shrink-0 bg-primary-500" />
            {t('home.heroBadge')}
          </p>

          <h1 className="mt-5 font-display text-[34px] font-light leading-[1.12] text-fg sm:text-5xl lg:text-[52px]">
            <Rich
              k="home.heroTitle"
              values={{
                highlight: <span className="text-primary-700">{t('home.heroHighlight')}</span>,
              }}
            />
          </h1>
          <p className="mt-5 text-sm leading-[1.8] text-ink-700 sm:mt-6 sm:text-base">
            {t('site.description')} {t('home.heroText')}
          </p>

          <div className="mt-6 flex min-h-[54px] flex-col gap-3 sm:mt-7 sm:flex-row sm:flex-wrap">
            {first && (
              <Button
                to={`/category/${first.slug}`}
                variant="primary"
                size="xl"
                className="max-sm:!h-[50px] max-sm:w-full"
              >
                {first.name}
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            )}
            {second && (
              <Button
                to={`/category/${second.slug}`}
                size="xl"
                variant="outline"
                className="max-sm:!h-[50px] max-sm:w-full"
              >
                {second.name}
              </Button>
            )}
          </div>
        </div>
        <HeroOrnament />
      </div>
    </section>
  );
}

/**
 * The glow disc, the double rhombus and the brand mark (DESIGN.md §7).
 * Decoration, from xl only: below that the category column leaves the hero
 * too narrow, and it would cover the text.
 */
function HeroOrnament() {
  return (
    <div
      aria-hidden="true"
      className="relative hidden h-[340px] w-[340px] shrink-0 items-center justify-center rounded-full bg-[radial-gradient(circle_at_50%_45%,rgb(var(--c-glow))_0%,rgb(var(--c-primary-50))_45%,rgb(var(--c-primary-50)/0)_70%)] text-primary-500 xl:flex"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 70 70"
        width="300"
        height="300"
        fill="none"
        stroke="currentColor"
        strokeWidth=".25"
        className="absolute"
      >
        <path d="M35 3 67 35 35 67 3 35z" strokeOpacity=".7" />
        <path d="M35 10 60 35 35 60 10 35z" strokeOpacity=".35" />
      </svg>
      <LogoMark size={96} />
    </div>
  );
}

function Benefits() {
  const { rules } = useDeliveryRules();
  // Mobile: a 2-column grid whose lines are the cells' own borders; lg: one
  // row, lines above and below and between the columns
  return (
    <section
      aria-label={t('home.benefits.label')}
      className="mt-5 grid grid-cols-2 border-l border-t border-line sm:mt-7 lg:grid-cols-4 lg:border-b lg:border-l-0"
    >
      {BENEFITS.map((benefit) => (
        <div
          key={benefit.title}
          className="flex flex-col items-start gap-2.5 border-b border-r border-line px-3.5 py-4 sm:flex-row sm:items-center sm:gap-4 lg:border-b-0 lg:border-r-0 lg:border-l lg:px-5 lg:py-6 lg:first:border-l-0"
        >
          <benefit.icon className="icon-fine h-7 w-7 shrink-0 text-primary-500" aria-hidden="true" />
          <span className="min-w-0">
            <span className="block font-serif text-[15px] font-medium text-fg">{t(benefit.title)}</span>
            <span className="mt-0.5 block text-xs text-fg-muted">
              {typeof benefit.text === 'function' ? benefit.text(rules) : t(benefit.text)}
            </span>
          </span>
        </div>
      ))}
    </section>
  );
}

function PopularCategories({ categories, loading }) {
  // Samsung belongs under Phones, not beside it - and its products are already
  // in the Phones count
  const roots = rootCategories(categories);
  // The grid's lines are the cells' own borders (DESIGN.md §4), so an
  // incomplete last row leaves no empty line-coloured cells
  const CELL = 'border-b border-r border-line bg-surface';

  return (
    <section className="pt-9 sm:pt-12">
      <h2 className="mb-4 font-serif text-[26px] font-light leading-[1.3] text-fg sm:mb-6 sm:text-[34px]">
        {t('home.popularCategories')}
      </h2>

      <div className="grid grid-cols-2 border-l border-t border-line sm:grid-cols-3 lg:grid-cols-6">
        {loading
          ? Array.from({ length: 6 }, (_, i) => (
              <div key={i} className={`${CELL} p-3 sm:p-[18px]`}>
                <Skeleton className="h-[170px]" rounded="rounded-card" />
              </div>
            ))
          : roots.map((category) => (
              <Link
                key={category.id}
                to={`/category/${category.slug}`}
                className={`group flex flex-col items-center gap-3.5 px-3 py-6 text-center transition-colors hover:bg-primary-50 sm:px-[18px] sm:py-9 ${CELL}`}
              >
                <CategoryIcon
                  name={category.icon}
                  framed
                  frameClassName="max-sm:-m-[7px] max-sm:scale-[0.8]"
                />
                <span className="font-serif text-[17px] leading-tight text-fg">{category.name}</span>
                <span className="text-xs text-fg-muted">{formatItemsCount(category.productsCount)}</span>
              </Link>
            ))}
      </div>
    </section>
  );
}
