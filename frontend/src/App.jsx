import { createBrowserRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';

import { appRoutes } from './routes.jsx';
import { basename, currentLanguage } from './i18n/index.js';

/**
 * The router, for the language the address is in.
 *
 * `/en/...` mounts the routes under the basename `/en`: inside, the path is
 * `/cart` as it is in Georgian, and every link and redirect the shop makes gets
 * `/en` put back in front of it. The language switch leaves this router - it
 * is a full page load - so one router never serves two languages.
 */
const language = currentLanguage();
const router = createBrowserRouter(appRoutes(language), { basename: basename(language) });

export default function App() {
  return <RouterProvider router={router} />;
}
