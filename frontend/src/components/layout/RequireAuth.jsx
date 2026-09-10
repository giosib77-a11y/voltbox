import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth.js';
import { Skeleton } from '../common/Skeleton.jsx';
import { QUERY_KEYS } from '../../constants/index.js';

/**
 * დაცული მარშრუტები. არაავტორიზებული მომხმარებელი გადამისამართდება
 * /login?redirect=<მიმდინარე გვერდი>-ზე.
 */
export default function RequireAuth() {
  const { isAuthenticated, initializing } = useAuth();
  const location = useLocation();

  if (initializing) {
    return (
      <div className="container-page py-10">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-6 h-64 w-full" rounded="rounded-card" />
      </div>
    );
  }

  if (!isAuthenticated) {
    const redirect = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?${QUERY_KEYS.redirect}=${encodeURIComponent(redirect)}`} replace />;
  }

  return <Outlet />;
}
