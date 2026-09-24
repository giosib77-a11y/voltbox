import { Link } from 'react-router';
import { ArrowRight, BadgePercent, Headphones, ShieldCheck, Truck, Zap } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import CategoryIcon from '../components/common/CategoryIcon.jsx';
import ProductCarousel from '../components/product/ProductCarousel.jsx';
import ErrorState from '../components/common/ErrorState.jsx';
import { Skeleton } from '../components/common/Skeleton.jsx';
import { useAsync } from '../hooks/useProducts.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import * as api from '../services/api.js';
import { HOME_SECTION_TITLES, SHIPPING, SITE_DESCRIPTION } from '../constants/index.js';
import { formatPrice } from '../utils/format.js';

const BENEFITS = [
  { icon: Truck, title: 'უფასო მიწოდება', text: `${formatPrice(SHIPPING.freeThreshold)}-ზე მეტ შეკვეთაზე` },
  { icon: ShieldCheck, title: 'ოფიციალური გარანტია', text: 'ყველა პროდუქტზე' },
  { icon: BadgePercent, title: 'საუკეთესო ფასი', text: 'რეგულარული ფასდაკლებები' },
  { icon: Headphones, title: 'კონსულტაცია', text: 'ორშ.–შაბ. 10:00–20:00' },
];

export default function Home() {
  useDocumentTitle('');
  const { data, loading, error, reload } = useAsync(() => api.getHomeSections(), []);

  const sections = data || {};

  return (
    <div className="container-page pb-12">
      <Hero />
      <Benefits />

      <PopularCategories categories={sections.popularCategories || []} loading={loading} />

      {error ? (
        <div className="py-8">
          <ErrorState error={error} onRetry={reload} />
        </div>
      ) : (
        <>
          <ProductCarousel
            title={HOME_SECTION_TITLES.newArrivals}
            products={sections.newArrivals || []}
            loading={loading}
          />
          <ProductCarousel
            title={HOME_SECTION_TITLES.discounted}
            products={sections.discounted || []}
            loading={loading}
          />
          <ProductCarousel
            title={HOME_SECTION_TITLES.featured}
            products={sections.featured || []}
            loading={loading}
          />
        </>
      )}
    </div>
  );
}

function Hero() {
  return (
    <section className="relative mt-4 overflow-hidden rounded-card border border-line bg-surface px-6 py-12 sm:px-10 sm:py-16 lg:px-14 lg:py-20">
      <div aria-hidden="true" className="bg-tech-grid absolute inset-0" />
      <div
        aria-hidden="true"
        className="absolute -right-24 -top-32 h-96 w-96 rounded-full bg-primary-200/70 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="absolute -bottom-40 left-1/4 h-72 w-72 rounded-full bg-primary-400/10 blur-3xl"
      />
      <HeroMark />

      <div className="relative max-w-2xl">
        <p className="inline-flex items-center gap-2 rounded-pill bg-primary-50 px-3 py-1 text-xs font-semibold text-primary-800 ring-1 ring-inset ring-primary-200">
          <BadgePercent className="h-3.5 w-3.5" aria-hidden="true" />
          სეზონური ფასდაკლებები — 30%-მდე
        </p>

        <h1 className="mt-5 text-3xl font-bold leading-tight tracking-tight text-fg sm:text-4xl lg:text-5xl">
          ტექნიკა, რომელიც{' '}
          <span className="bg-gradient-to-r from-primary-700 to-primary-500 bg-clip-text text-transparent">
            ყოველდღე
          </span>{' '}
          გჭირდება
        </h1>
        <p className="mt-4 max-w-lg text-sm leading-relaxed text-ink-600 sm:text-base">
          {SITE_DESCRIPTION} ორიგინალი პროდუქცია ოფიციალური გარანტიით და მიწოდებით მთელ საქართველოში.
        </p>

        <div className="mt-7 flex flex-wrap gap-3">
          <Button to="/category/phones" variant="primary" size="lg" className="shadow-glow">
            ტელეფონების ნახვა
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button to="/category/headphones" size="lg" variant="outline">
            ყურსასმენები
          </Button>
        </div>
      </div>
    </section>
  );
}

/** The bolt in rings on the right of the hero. Decoration, large screens only. */
function HeroMark() {
  return (
    <div
      aria-hidden="true"
      className="absolute right-12 top-1/2 hidden -translate-y-1/2 lg:block xl:right-20"
    >
      <div className="relative flex h-72 w-72 items-center justify-center rounded-full border border-primary-500/15">
        <div className="absolute inset-8 rounded-full border border-primary-500/25" />
        <div className="absolute inset-16 rounded-full bg-primary-600/20 blur-2xl" />
        <span className="relative flex h-24 w-24 items-center justify-center rounded-3xl bg-gradient-to-br from-primary-400 to-primary-600 text-white shadow-[0_0_64px_-8px] shadow-primary-500/70 ring-1 ring-inset ring-white/20">
          <Zap className="h-12 w-12" fill="currentColor" />
        </span>
      </div>
    </div>
  );
}

function Benefits() {
  return (
    <section aria-label="ჩვენი უპირატესობები" className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {BENEFITS.map((benefit) => (
        <div
          key={benefit.title}
          className="flex flex-col items-start gap-2.5 rounded-card border border-line bg-surface p-3.5 sm:flex-row sm:gap-3"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-primary-50 text-primary-700 ring-1 ring-inset ring-primary-200">
            <benefit.icon className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-fg">{benefit.title}</span>
            <span className="block text-xs text-fg-muted">{benefit.text}</span>
          </span>
        </div>
      ))}
    </section>
  );
}

function PopularCategories({ categories, loading }) {
  return (
    <section className="pt-10 sm:pt-12">
      <h2 className="mb-4 text-xl font-bold tracking-tight text-fg sm:mb-5 sm:text-2xl">
        {HOME_SECTION_TITLES.popularCategories}
      </h2>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {loading
          ? Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-28" rounded="rounded-card" />
            ))
          : categories.map((category) => (
              <Link
                key={category.id}
                to={`/category/${category.slug}`}
                className="group flex flex-col items-center gap-2.5 rounded-card border border-line bg-surface p-4 text-center transition-all hover:-translate-y-0.5 hover:border-primary-400 hover:shadow-glow"
              >
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-50 text-primary-700 ring-1 ring-inset ring-primary-200 transition-colors group-hover:bg-primary-600 group-hover:text-white group-hover:ring-transparent">
                  <CategoryIcon name={category.icon} className="h-6 w-6" />
                </span>
                <span className="text-sm font-semibold leading-tight text-fg">{category.name}</span>
                <span className="text-xs text-fg-muted">{category.productsCount} პროდუქტი</span>
              </Link>
            ))}
      </div>
    </section>
  );
}
