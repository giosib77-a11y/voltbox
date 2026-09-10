import { useRef } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import ProductCard from './ProductCard.jsx';
import { ProductCardSkeleton } from '../common/Skeleton.jsx';
import { TEXT } from '../../constants/index.js';

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
    <section className="py-8 sm:py-10">
      <div className="mb-4 flex items-end justify-between gap-4 sm:mb-5">
        <h2 className="text-xl font-bold tracking-tight text-ink-900 sm:text-2xl">{title}</h2>

        <div className="flex items-center gap-2">
          {viewAllTo && (
            <Link
              to={viewAllTo}
              className="rounded-sm text-sm font-semibold text-primary-700 underline-offset-4 hover:underline"
            >
              {TEXT.viewAll}
            </Link>
          )}
          <div className="hidden gap-1.5 lg:flex">
            <button
              type="button"
              onClick={() => scrollBy(-1)}
              aria-label="წინა პროდუქტები"
              className="flex h-9 w-9 items-center justify-center rounded-control border border-ink-300 bg-white text-ink-600 transition-colors hover:border-primary-400 hover:text-primary-700"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => scrollBy(1)}
              aria-label="შემდეგი პროდუქტები"
              className="flex h-9 w-9 items-center justify-center rounded-control border border-ink-300 bg-white text-ink-600 transition-colors hover:border-primary-400 hover:text-primary-700"
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>

      <div ref={scrollerRef} className="scroll-row lg:grid lg:grid-cols-4 lg:gap-4 lg:overflow-visible">
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
