import { Skeleton, ProductGridSkeleton } from '../common/Skeleton.jsx';

/**
 * `<Suspense>`-ის fallback მარშრუტებს შორის გადასვლისას.
 *
 * გვერდები დინამიურად იტვირთება (`React.lazy`), ამიტომ chunk-ის ჩამოტვირთვისას
 * წამიერი პაუზაა. ცარიელი ეკრანის ნაცვლად ვაჩვენებთ იმავე გეომეტრიის skeleton-ს,
 * რასაც კატალოგი — ასე გადასვლა შეუმჩნეველია და layout არ ხტება.
 */
export default function PageFallback() {
  return (
    <div className="container-page py-5 lg:py-7" role="status" aria-label="იტვირთება">
      <Skeleton className="h-4 w-52" />
      <Skeleton className="mt-4 h-8 w-72" />
      <div className="mt-7">
        <ProductGridSkeleton count={8} />
      </div>
      <span className="sr-only">გვერდი იტვირთება…</span>
    </div>
  );
}
