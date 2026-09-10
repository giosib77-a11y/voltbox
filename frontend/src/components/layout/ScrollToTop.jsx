import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * მარშრუტის ცვლილებაზე გვერდი ზემოდან იწყება.
 * query-params-ის ცვლილება (ფილტრები) სქროლს არ ცვლის.
 */
export default function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [pathname]);

  return null;
}
