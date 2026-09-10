/**
 * AdminUnavailable: shown when the build runs against mock data.
 *
 * What it does: explains that the panel needs the real backend and how to
 * switch, instead of rendering a shell whose every request would fail.
 * Where it fits: rendered for every /admin route when VITE_API_MODE is not http.
 */

import { Link } from 'react-router-dom';
import { PlugZap } from 'lucide-react';

export default function AdminUnavailable() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
      <div className="w-full max-w-lg text-center">
        <PlugZap className="mx-auto h-12 w-12 text-ink-500" aria-hidden="true" />
        <h1 className="mt-4 text-xl font-semibold text-ink-900">
          ადმინ პანელს backend სჭირდება
        </h1>
        <p className="mt-2 text-sm text-ink-600">
          ეს ბილდი <code className="rounded bg-ink-100 px-1">mock</code> რეჟიმშია — მონაცემები
          მეხსიერებიდან მოდის. ადმინ პანელი რეალურ მონაცემებს მართავს, ამიტომ mock რეჟიმში
          განზრახ არ მუშაობს.
        </p>
        <pre className="mt-4 overflow-x-auto rounded-lg bg-ink-900 p-4 text-left text-xs text-ink-100">
          {`# frontend/.env
VITE_API_MODE=http
VITE_API_BASE_URL=/api/v1`}
        </pre>
        <p className="mt-3 text-xs text-ink-500">
          შემდეგ გაუშვი backend (<code>uvicorn app.main:app</code>) და dev-სერვერი თავიდან.
        </p>
        <Link
          to="/"
          className="mt-6 inline-block rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700"
        >
          მაღაზიაში დაბრუნება
        </Link>
      </div>
    </main>
  );
}
