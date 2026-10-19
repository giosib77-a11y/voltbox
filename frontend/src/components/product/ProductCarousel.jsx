import { useRef } from 'react';
import { Link } from 'react-router';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import ProductCard from './ProductCard.jsx';
import { ProductCardSkeleton } from '../common/Skeleton.jsx';
import { t } from '../../i18n/index.js';

/**
 * მთავარი გვერდის სექცია: mobile-ზე ჰორიზონტალური carousel, desktop-ზე grid.
 */
export default function ProductCarousel({
  title,
  products = [],
  loading = false,
  viewAllTo = '',
  skeletonCount = 4,
}) {
  const scrollerRef = useRef(null);

  function scrollBy(direction) {
    const node = scrollerRef.current;
    if (!node) return;
    node.scrollBy({ left: direction * (node.clientWidth * 0.8), behavior: 'smooth' });
  }

  if (!loading && products.length === 0) return null;

  return (
    <section className="pt-9 sm:pt-12">
      <div className="mb-4 flex items-end justify-between gap-4 sm:mb-6">
        <h2 className="font-serif text-[26px] font-light leading-[1.3] text-fg sm:text-[34px]">{title}</h2>

        <div className="flex items-center gap-2">
          {viewAllTo && (
            <Link
              to={viewAllTo}
              className="rounded-sm text-sm font-semibold text-primary-700 underline-offset-4 hover:underline"
            >
              {t('common.viewAll')}
            </Link>
          )}
          <div className="hidden gap-2.5 lg:flex">
            <button
              type="button"
              onClick={() => scrollBy(-1)}
              aria-label={t('carousel.previous')}
              className="flex h-[46px] w-[46px] items-center justify-center rounded-pill border border-outline bg-transparent text-fg transition-colors hover:border-primary-500 hover:bg-primary-50 hover:text-primary-700 active:bg-primary-100"
            >
              <ChevronLeft className="h-[18px] w-[18px]" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => scrollBy(1)}
              aria-label={t('carousel.next')}
              className="flex h-[46px] w-[46px] items-center justify-center rounded-pill border border-outline bg-transparent text-fg transition-colors hover:border-primary-500 hover:bg-primary-50 hover:text-primary-700 active:bg-primary-100"
            >
              <ChevronRight className="h-[18px] w-[18px]" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>

      <div ref={scrollerRef} className="scroll-row lg:grid lg:grid-cols-4 lg:gap-6 lg:overflow-visible">
        {loading
          ? Array.from({ length: skeletonCount }, (_, i) => (
              <div key={i} className="w-[62vw] shrink-0 snap-start sm:w-[42vw] md:w-[32vw] lg:w-auto">
                <ProductCardSkeleton />
              </div>
            ))
          : products.map((product) => (
              <div
                key={product.id}
                className="w-[62vw] shrink-0 snap-start sm:w-[42vw] md:w-[32vw] lg:w-auto"
              >
                <ProductCard product={product} />
              </div>
            ))}
      </div>
    </section>
  );
}
