import { lazy } from 'react';
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';

import Layout from './components/layout/Layout.jsx';
import RequireAuth from './components/layout/RequireAuth.jsx';
import AdminBoundary from './admin/AdminBoundary.jsx';

/**
 * გვერდები იტვირთება მოთხოვნისამებრ (`React.lazy`) — Vite თითოეულს ცალკე
 * chunk-ად ჭრის. Layout, Header, Footer და საერთო კომპონენტები რჩება მთავარ
 * ბანდლში, რადგან ისინი ყველა მარშრუტზე საჭიროა.
 *
 * `<Suspense>` და მისი skeleton-fallback `components/layout/Layout.jsx`-შია.
 */
const Home = lazy(() => import('./pages/Home.jsx'));
const Category = lazy(() => import('./pages/Category.jsx'));
const ProductDetails = lazy(() => import('./pages/ProductDetails.jsx'));
const SearchResults = lazy(() => import('./pages/SearchResults.jsx'));
const Cart = lazy(() => import('./pages/Cart.jsx'));
const Checkout = lazy(() => import('./pages/Checkout.jsx'));
const CheckoutSuccess = lazy(() => import('./pages/CheckoutSuccess.jsx'));
const Login = lazy(() => import('./pages/Login.jsx'));
const Register = lazy(() => import('./pages/Register.jsx'));
const NotFound = lazy(() => import('./pages/NotFound.jsx'));
const AccountLayout = lazy(() => import('./pages/Account/AccountLayout.jsx'));
const Orders = lazy(() => import('./pages/Account/Orders.jsx'));
const Profile = lazy(() => import('./pages/Account/Profile.jsx'));
const Addresses = lazy(() => import('./pages/Account/Addresses.jsx'));
const ChangePassword = lazy(() => import('./pages/Account/ChangePassword.jsx'));

/**
 * ადმინის მარშრუტები.
 *
 * ყველა `lazy()` განზრახ ამ ფუნქციის შიგნითაა და არა მოდულის დონეზე:
 * `import.meta.env.VITE_API_MODE` ბილდის დროს კონსტანტად ჩანაცვლდება, ამიტომ
 * mock-ბილდში ქვემოთა ტოტი მკვდარი კოდია და Rollup მასთან ერთად ადმინის
 * `import()`-ებსაც აგდებს — მაღაზიის ბილდში ადმინის chunk-ები საერთოდ არ ჩნდება.
 *
 * ადმინი მხოლოდ `http` რეჟიმში მუშაობს: ის რეალურ მონაცემებს მართავს და mock-ზე
 * მისი გაყალბება ვერაფერს დაამტკიცებდა მარაგისა და აუდიტის წესებზე.
 */
function adminChildren() {
  if (import.meta.env?.VITE_API_MODE !== 'http') {
    const AdminUnavailable = lazy(() => import('./admin/pages/AdminUnavailable.jsx'));
    return [{ path: '*', element: <AdminUnavailable /> }];
  }

  const AdminLogin = lazy(() => import('./admin/pages/AdminLogin.jsx'));
  const AdminLayout = lazy(() => import('./admin/AdminLayout.jsx'));
  const AdminDashboard = lazy(() => import('./admin/pages/AdminDashboard.jsx'));
  const RequireAdmin = lazy(() => import('./admin/RequireAdmin.jsx'));

  return [
    { path: 'login', element: <AdminLogin /> },
    {
      element: <RequireAdmin />,
      children: [
        {
          element: <AdminLayout />,
          children: [{ index: true, element: <AdminDashboard /> }],
        },
      ],
    },
  ];
}

const adminRoutes = {
  path: '/admin',
  // საკუთარი Suspense — მაღაზიის Layout-ს ადმინი არ იყენებს
  element: <AdminBoundary />,
  children: adminChildren(),
};

/**
 * მარშრუტების ერთადერთი აღწერა.
 * გვერდები lazy-ია; Layout და RequireAuth — არა (ყოველთვის საჭიროა).
 * `future` ალმები v7-ის ქცევას რთავს — ამით dev-console სუფთა რჩება.
 */
const router = createBrowserRouter(
  [
    // ადმინს მაღაზიის Layout (header/footer) არ სჭირდება — ცალკე ხეა
    adminRoutes,
    {
      path: '/',
      element: <Layout />,
      children: [
        { index: true, element: <Home /> },
        { path: 'category/:slug', element: <Category /> },
        { path: 'product/:slug', element: <ProductDetails /> },
        { path: 'search', element: <SearchResults /> },
        { path: 'cart', element: <Cart /> },
        { path: 'checkout', element: <Checkout /> },
        { path: 'checkout/success/:id', element: <CheckoutSuccess /> },
        { path: 'login', element: <Login /> },
        { path: 'register', element: <Register /> },
        {
          path: 'account',
          element: <RequireAuth />,
          children: [
            {
              element: <AccountLayout />,
              children: [
                { index: true, element: <Navigate to="/account/orders" replace /> },
                { path: 'orders', element: <Orders /> },
                { path: 'profile', element: <Profile /> },
                { path: 'addresses', element: <Addresses /> },
                { path: 'password', element: <ChangePassword /> },
              ],
            },
          ],
        },
        { path: '*', element: <NotFound /> },
      ],
    },
  ],
  {
    future: {
      v7_relativeSplatPath: true,
      v7_fetcherPersist: true,
      v7_normalizeFormMethod: true,
      v7_partialHydration: true,
      v7_skipActionErrorRevalidation: true,
    },
  },
);

export default function App() {
  return <RouterProvider router={router} future={{ v7_startTransition: true }} />;
}
