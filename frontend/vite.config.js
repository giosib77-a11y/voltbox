import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

/**
 * ტუნელის სერვისების დომენები.
 *
 * Vite 5.4+ ამოწმებს `Host` header-ს (DNS-rebinding-ისგან დასაცავად) და უცნობ
 * დომენს „Blocked request“-ით აბრუნებს. ngrok/cloudflared-ით გაზიარებისთვის
 * ეს დომენები აშკარად უნდა იყოს დაშვებული.
 *
 * `true`-ს განზრახ არ ვწერთ — ის ნებისმიერ host-ს უშვებს და დაცვას აზრს უკარგავს.
 */
const TUNNEL_HOSTS = [
  '.ngrok-free.app',
  '.ngrok-free.dev',
  '.ngrok.app',
  '.ngrok.io',
  '.trycloudflare.com',
  '.loca.lt',
];

/**
 * API-ს proxy — `/api/*` ლოკალურ backend-ზე გადამისამართდება.
 *
 * ორი პრობლემას ხსნის ერთდროულად:
 *
 * 1. **გაზიარება.** ngrok მხოლოდ frontend-ის პორტს გამოაქვს. სტუმრის
 *    ბრაუზერისთვის `localhost:8000` მისივე კომპიუტერია — API-ს ვერ ნახავდა.
 *    proxy-ით მოთხოვნა იმავე ტუნელით მიდის და სერვერზე გადამისამართდება.
 * 2. **CORS.** ბრაუზერისთვის მოთხოვნა იმავე origin-ზეა, ამიტომ preflight
 *    საერთოდ არ ხდება და `CORS_ORIGINS`-ში ტუნელის დომენის დამატება არ სჭირდება.
 *
 * გასააქტიურებლად `.env`-ში `VITE_API_BASE_URL` **შედარებითი** უნდა იყოს
 * (`/api/v1`). აბსოლუტური მისამართისას (`http://localhost:8000/api/v1`)
 * ბრაუზერი პირდაპირ მიდის და proxy-ს გვერდს უვლის.
 */
const API_PROXY = {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
  },
};

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // `npm run dev:share` → mode === 'share': ტუნელისთვის მორგებული dev-სერვერი
  const isShared = mode === 'share';

  /**
   * Data layer-ის გადამრთველი — ბილდის დროს.
   *
   * `services/api.js` აიმპორტებს ერთადერთ სპეციფიკატორს `virtual:api-impl`,
   * რომელიც აქ იხსნება კონკრეტულ ფაილად. შედეგად მოდულების გრაფში მხოლოდ
   * *ერთი* იმპლემენტაცია ხვდება: mock რეჟიმში `httpApi.js` საერთოდ არ არსებობს,
   * http რეჟიმში კი `mockApi.js` და მისი 61-პროდუქტიანი ბაზა (~127 KB) იშლება.
   *
   * ეს tree-shaking-ზე დაყრდნობას სჯობს: Rollup `products.js`-ის მოდულის
   * დონეზე `.map()`-ს პოტენციურ side effect-ად თვლის და ვერ აგდებს.
   */
  // monorepo-ში ბრძანება repo-ს ძირიდანაც შეიძლება გაეშვას
  // (`vite build --config frontend/vite.config.js`). `process.cwd()` მაშინ
  // არასწორ დირექტორიას მიუთითებდა: `.env` ვერ მოიძებნებოდა და
  // `VITE_API_MODE=http` ჩუმად `mock`-ად წაიკითხებოდა — შეცდომის გარეშე,
  // უბრალოდ არასწორი ბანდლით. კონფიგის საკუთარი დირექტორია ყოველთვის სწორია.
  const rootDir = fileURLToPath(new URL('.', import.meta.url));
  const env = loadEnv(mode, rootDir, '');
  const apiMode = env.VITE_API_MODE === 'http' ? 'http' : 'mock';

  /**
   * Where the shop will live, for the tags that need an absolute URL.
   *
   * Open Graph images and canonical links cannot be relative — a crawler reads
   * them out of context and has nothing to resolve them against.
   *
   * `__SITE_URL__` rather than Vite's own `%VITE_SITE_URL%` for two reasons.
   * Vite leaves the literal text in place when the variable is unset, which
   * would publish `%VITE_SITE_URL%/og-image.png` as an image URL; and inside an
   * `href` the build fails outright with "URI malformed", because it runs
   * decodeURI over the attribute and `%VI` is not a valid escape.
   *
   * Unset falls back to the local address and says so in a production build.
   */
  const siteUrl = (env.VITE_SITE_URL || 'http://localhost:5173').replace(/\/+$/, '');
  const siteUrlPlugin = {
    name: 'voltbox-site-url',
    // `this.warn` rather than console: it is the channel the build already
    // uses, so the line appears with the rest of Vite's output and once.
    buildStart() {
      if (mode === 'production' && !env.VITE_SITE_URL) {
        this.warn(
          `VITE_SITE_URL is not set. Shared links and canonical URLs will point at ${siteUrl}` +
            ' — see docs/pre-deployment-checklist.md §15.',
        );
      }
    },
    transformIndexHtml(html) {
      return html.replaceAll('__SITE_URL__', siteUrl);
    },
  };
  const apiImpl = apiMode === 'http' ? './src/services/httpApi.js' : './src/services/mockApi.js';

  return {
    root: rootDir,
    envDir: rootDir,
    plugins: [react(), siteUrlPlugin],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        'virtual:api-impl': fileURLToPath(new URL(apiImpl, import.meta.url)),
      },
    },
    server: {
      port: 5173,
      open: false,
      host: isShared ? true : undefined,
      allowedHosts: TUNNEL_HOSTS,
      // ტუნელი https-ზე მუშაობს, ამიტომ HMR-ის websocket 443-ზე უნდა წავიდეს.
      // ლოკალურ რეჟიმში ეს არ ეხება — თორემ HMR localhost:443-ს დაუკავშირდებოდა.
      hmr: isShared ? { protocol: 'wss', clientPort: 443 } : undefined,
      proxy: API_PROXY,
    },
    preview: {
      port: 4173,
      allowedHosts: TUNNEL_HOSTS,
      proxy: API_PROXY,
    },
    test: {
      // jsdom — კომპონენტების ტესტებს DOM სჭირდებათ
      environment: 'jsdom',
      globals: true,
      setupFiles: [fileURLToPath(new URL('./vitest.setup.js', import.meta.url))],
      include: ['src/**/*.test.{js,jsx}'],
      restoreMocks: true,
    },
  };
});
