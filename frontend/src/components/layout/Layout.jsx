import { Suspense } from 'react';
import { Outlet } from 'react-router-dom';
import Header from './Header.jsx';
import Footer from './Footer.jsx';
import ScrollToTop from './ScrollToTop.jsx';
import PageFallback from './PageFallback.jsx';
import ToastViewport from '../common/Toast.jsx';
import { useCategories } from '../../hooks/useProducts.js';

/**
 * აპლიკაციის მთავარი კარკასი — header, კონტენტი, footer, toast-ები.
 * კატეგორიები ერთხელ იტვირთება და გადაეცემა header-სა და footer-ს.
 */
export default function Layout() {
  const { data: categories } = useCategories();

  return (
    <div className="flex min-h-screen flex-col bg-ink-50">
      <a href="#main-content" className="skip-link">
        მთავარ კონტენტზე გადასვლა
      </a>

      <ScrollToTop />
      <Header categories={categories || []} />

      <main id="main-content" className="flex-1">
        <Suspense fallback={<PageFallback />}>
          <Outlet />
        </Suspense>
      </main>

      <Footer categories={categories || []} />
      <ToastViewport />
    </div>
  );
}
