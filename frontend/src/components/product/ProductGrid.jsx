import ProductCard from './ProductCard.jsx';
import { ProductGridSkeleton } from '../common/Skeleton.jsx';
import EmptyState from '../common/EmptyState.jsx';
import ErrorState from '../common/ErrorState.jsx';

/**
 * პროდუქტების ბადე სამივე მდგომარეობით: loading → success → error/empty.
 * სვეტები: mobile 2 / tablet 3 / desktop 4.
 */
export default function ProductGrid({
  products = [],
  loading = false,
  error = null,
  onRetry = null,
  skeletonCount = 8,
  emptyProps = {},
  className = '',
}) {
  if (loading) return <ProductGridSkeleton count={skeletonCount} />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (!products.length) return <EmptyState {...emptyProps} />;

  return (
    <div className={`grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4 ${className}`}>
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}
