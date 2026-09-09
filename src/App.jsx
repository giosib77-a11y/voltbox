import { lazy } from 'react';
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';

import Layout from './components/layout/Layout.jsx';
import RequireAuth from './components/layout/RequireAuth.jsx';

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
 * მარშრუტების ერთადერთი აღწერა.
 * გვერდები lazy-ია; Layout და RequireAuth — არა (ყოველთვის საჭიროა).
 * `future` ალმები v7-ის ქცევას რთავს — ამით dev-console სუფთა რჩება.
 */
const router = createBrowserRouter(
  [
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
