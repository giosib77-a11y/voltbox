import { Link } from 'react-router-dom';
import { ArrowRight, BadgePercent, Headphones, ShieldCheck, Truck } from 'lucide-react';
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
    <section className="relative mt-4 overflow-hidden rounded-card bg-gradient-to-br from-primary-800 via-primary-700 to-primary-900 px-6 py-12 text-white sm:px-10 sm:py-16 lg:px-14 lg:py-20">
      <div
        aria-hidden="true"
        className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-accent-500/25 blur-2xl sm:h-80 sm:w-80"
      />
      <div
        aria-hidden="true"
        className="absolute -bottom-24 -left-10 h-56 w-56 rounded-full bg-primary-400/25 blur-3xl"
      />

      <div className="relative max-w-2xl">
        <p className="inline-flex items-center gap-2 rounded-pill bg-white/15 px-3 py-1 text-xs font-semibold backdrop-blur">
          <BadgePercent className="h-3.5 w-3.5" aria-hidden="true" />
          სეზონური ფასდაკლებები — 30%-მდე
        </p>

        <h1 className="mt-4 text-3xl font-bold leading-tight tracking-tight sm:text-4xl lg:text-5xl">
          ტექნიკა, რომელიც ყოველდღე გჭირდება
        </h1>
        <p className="mt-4 max-w-lg text-sm leading-relaxed text-primary-100 sm:text-base">
          {SITE_DESCRIPTION} ორიგინალი პროდუქცია ოფიციალური გარანტიით და მიწოდებით მთელ საქართველოში.
        </p>

        <div className="mt-7 flex flex-wrap gap-3">
          <Button to="/category/phones" variant="accent" size="lg">
            ტელეფონების ნახვა
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            to="/category/headphones"
            size="lg"
            className="border border-white/30 bg-white/10 text-white hover:bg-white/20"
            variant="ghost"
          >
            ყურსასმენები
          </Button>
        </div>
      </div>
    </section>
  );
}

function Benefits() {
  return (
    <section aria-label="ჩვენი უპირატესობები" className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {BENEFITS.map((benefit) => (
        <div
          key={benefit.title}
          className="flex items-start gap-3 rounded-card border border-ink-200 bg-white p-3.5"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-primary-50 text-primary-700">
            <benefit.icon className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-ink-900">{benefit.title}</span>
            <span className="block text-xs text-ink-500">{benefit.text}</span>
          </span>
        </div>
      ))}
    </section>
  );
}

function PopularCategories({ categories, loading }) {
  return (
    <section className="pt-10 sm:pt-12">
      <h2 className="mb-4 text-xl font-bold tracking-tight text-ink-900 sm:mb-5 sm:text-2xl">
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
                className="group flex flex-col items-center gap-2.5 rounded-card border border-ink-200 bg-white p-4 text-center transition-all hover:-translate-y-0.5 hover:border-primary-300 hover:shadow-card-hover"
              >
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-50 text-primary-700 transition-colors group-hover:bg-primary-600 group-hover:text-white">
                  <CategoryIcon name={category.icon} className="h-6 w-6" />
                </span>
                <span className="text-sm font-semibold leading-tight text-ink-900">{category.name}</span>
                <span className="text-xs text-ink-500">{category.productsCount} პროდუქტი</span>
              </Link>
            ))}
      </div>
    </section>
  );
}
