/**
 * Skeleton-ები — spinner-ის ნაცვლად.
 * shimmer ეფექტი Tailwind-ის keyframes-იდან.
 */
export function Skeleton({ className = '', rounded = 'rounded-md' }) {
  return (
    <div
      className={`relative overflow-hidden bg-ink-200/70 ${rounded} ${className}`}
      aria-hidden="true"
    >
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-surface/60 to-transparent" />
    </div>
  );
}

/** პროდუქტის ბარათის skeleton — ProductCard-ის იდენტური გეომეტრიით (DESIGN.md §6). */
export function ProductCardSkeleton() {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-card border border-line bg-surface">
      <Skeleton className="aspect-square w-full border-b border-line" rounded="rounded-none" />
      <div className="flex flex-1 flex-col gap-2 p-3.5 sm:p-[22px]">
        <Skeleton className="h-3.5 w-16" rounded="rounded-control" />
        <Skeleton className="h-4 w-full" rounded="rounded-control" />
        <Skeleton className="h-4 w-3/4" rounded="rounded-control" />
        <Skeleton className="h-3 w-1/2" rounded="rounded-control" />
        <div className="mt-auto flex flex-col gap-3 pt-2">
          <Skeleton className="h-7 w-24" rounded="rounded-control" />
          <Skeleton className="h-11 w-full sm:h-[50px]" rounded="rounded-control" />
        </div>
      </div>
    </div>
  );
}

/** Same columns as ProductGrid. */
export function ProductGridSkeleton({ count = 8 }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 xl:grid-cols-4 xl:gap-6">
      {Array.from({ length: count }, (_, i) => (
        <ProductCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function TextSkeleton({ lines = 3 }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={`h-3.5 ${i === lines - 1 ? 'w-2/3' : 'w-full'}`} />
      ))}
    </div>
  );
}

export default Skeleton;
