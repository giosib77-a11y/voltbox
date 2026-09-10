import { Home, Search } from 'lucide-react';
import Button from '../components/common/Button.jsx';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';

/** 404 — ყველა უცნობი მარშრუტისთვის. */
export default function NotFound() {
  useDocumentTitle('გვერდი ვერ მოიძებნა');

  return (
    <div className="container-page flex min-h-[60vh] flex-col items-center justify-center py-14 text-center">
      <p className="text-7xl font-bold tracking-tight text-primary-600 sm:text-8xl">404</p>
      <h1 className="mt-4 text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
        გვერდი ვერ მოიძებნა
      </h1>
      <p className="mt-2.5 max-w-md text-sm leading-relaxed text-ink-600">
        შესაძლოა მისამართი შეიცვალა ან გვერდი წაიშალა. სცადეთ მთავარი გვერდიდან დაწყება ან
        მოძებნეთ პროდუქტი.
      </p>

      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <Button to="/" size="lg">
          <Home className="h-4 w-4" aria-hidden="true" />
          მთავარი გვერდი
        </Button>
        <Button to="/search" variant="outline" size="lg">
          <Search className="h-4 w-4" aria-hidden="true" />
          ძებნა
        </Button>
      </div>
    </div>
  );
}
