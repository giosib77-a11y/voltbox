import { Suspense, useLayoutEffect } from 'react';
import { Outlet } from 'react-router';
import Header from './Header.jsx';
import Footer from './Footer.jsx';
import ScrollToTop from './ScrollToTop.jsx';
import PageFallback from './PageFallback.jsx';
import ToastViewport from '../common/Toast.jsx';
import { useCategories } from '../../hooks/useProducts.js';
import { useTheme } from '../../hooks/useTheme.js';
import { applyTheme } from '../../utils/theme.js';

/**
 * აპლიკაციის მთავარი კარკასი — header, კონტენტი, footer, toast-ები.
 * კატეგორიები ერთხელ იტვირთება და გადაეცემა header-სა და footer-ს.
 */
export default function Layout() {
  const { data: categories } = useCategories();
  const [theme] = useTheme();

  // public/theme-init.js set the class before the first paint; this keeps it
  // right after a pick, a change in the system setting, or a visit that began
  // in the admin (which the script skips). Before paint, so no frame shows the
  // old theme. Left in place on unmount: `data-admin` overrides it.
  useLayoutEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // min-h-dvh behind a @supports guard, with 100vh as the fallback.
  //
  // On mobile Safari and Chrome, 100vh is the height of the viewport with the
  // browser chrome hidden, which is taller than what is actually on screen - so
  // a short page (an empty cart, a 404) ends up a little taller than the phone
  // and scrolls for no reason. `dvh` is the visible height. The guard keeps the
  // old behaviour on a browser that does not know the unit, where dropping to
  // `auto` would let the footer float up the page.
  return (
    <div data-storefront className="flex min-h-screen flex-col bg-canvas text-fg [@supports(min-height:100dvh)]:min-h-[100dvh]">
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
