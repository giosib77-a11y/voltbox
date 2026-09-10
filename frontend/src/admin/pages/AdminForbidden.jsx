/**
 * AdminForbidden: shown when a signed-in user has no admin role.
 *
 * What it does: explains the refusal and offers the two useful ways out.
 * Where it fits: rendered by RequireAdmin for the `forbidden` state.
 */

import { Link } from 'react-router-dom';
import { ShieldX } from 'lucide-react';

export default function AdminForbidden() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
      <div className="w-full max-w-md text-center">
        <ShieldX className="mx-auto h-12 w-12 text-ink-500" aria-hidden="true" />
        <h1 className="mt-4 text-xl font-semibold text-ink-900">წვდომა შეზღუდულია</h1>
        <p className="mt-2 text-sm text-ink-600">
          თქვენი ანგარიში ადმინისტრატორი არ არის. თუ ეს შეცდომაა, მიმართეთ მაღაზიის
          ადმინისტრატორს.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link
            to="/"
            className="rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700"
          >
            მაღაზიაში დაბრუნება
          </Link>
          <Link
            to="/admin/login"
            className="rounded-lg border border-ink-300 px-4 py-2 text-sm font-medium text-ink-700 hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-500"
          >
            სხვა ანგარიშით შესვლა
          </Link>
        </div>
      </div>
    </main>
  );
}
