# VoltBox — ონლაინ-მაღაზიის Frontend

> monorepo-ს ნაწილი. ზოგადი მიმოხილვა — [`../README.md`](../README.md),
> სერვერის მხარე — [`../backend/README.md`](../backend/README.md).

ელექტრონიკისა და აქსესუარების მაღაზიის სრულად ფუნქციური frontend: React 18 + Vite +
Tailwind CSS. Backend **არ არსებობს** — მონაცემები mock წყაროდან მოდის, მაგრამ
არქიტექტურა ისეა აწყობილი, რომ REST API-ზე გადასვლა ხდება **მხოლოდ ერთი ფენის
(`services/`) ჩანაცვლებით**, კომპონენტების გადაწერის გარეშე.

ინტერფეისის ენა — ქართული, ვალუტა — ₾ (GEL).

---

## შინაარსი

- [გაშვება](#გაშვება)
- [ტექნოლოგიური სტეკი](#ტექნოლოგიური-სტეკი)
- [არქიტექტურა](#არქიტექტურა)
- [Backend-ზე გადასვლა](#backend-ზე-გადასვლა)
- [პროექტის სტრუქტურა](#პროექტის-სტრუქტურა)
- [მონაცემთა კონტრაქტი](#მონაცემთა-კონტრაქტი)
- [ახალი კატეგორიის დამატება](#ახალი-კატეგორიის-დამატება)
- [ძებნის ალგორითმი](#ძებნის-ალგორითმი)
- [URL-ის მდგომარეობა](#urlის-მდგომარეობა)
- [Bundle და code splitting](#bundle-და-code-splitting)
- [დიზაინ-ტოკენები](#დიზაინ-ტოკენები)
- [localStorage](#localstorage)

---

## გაშვება

```bash
cd frontend        # ← ყველა ქვემოთ მოცემული ბრძანება აქედან სრულდება
npm install
npm run dev        # http://localhost:5173
```

სხვა ბრძანებები:

```bash
npm run build        # პროდაქშენ ბილდი → dist/
npm run preview      # ბილდის ლოკალური გადახედვა
npm run gen:images   # პროდუქტების placeholder-სურათების ხელახლა გენერაცია
```

მოთხოვნა: Node.js 18+.

---

## ტექნოლოგიური სტეკი

| ფენა | არჩევანი |
|---|---|
| Build | Vite 5 |
| UI | React 18 (JSX, ფუნქციური კომპონენტები + hooks) |
| Styling | Tailwind CSS 3 (utility-first) |
| Routing | React Router v6 (`createBrowserRouter`) |
| State | Context + `useReducer` (Cart, Auth, Toast) |
| Icons | `lucide-react` |
| Persistence | `localStorage` |

გარე UI-კიტები, Redux/MobX და backend-ზე რეალური მოთხოვნები არ გამოიყენება.

---

## არქიტექტურა

```
UI (pages / components)
        │  იძახებს მხოლოდ:
        ▼
services/api.js          ← საჯარო კონტრაქტი (ყოველთვის async → Promise)
        │
        ├── services/mockApi.js   (VITE_API_MODE=mock)  → data/ + utils/
        └── services/httpApi.js   (VITE_API_MODE=http)  → fetch → REST
```

**მთავარი წესი:** არცერთი გვერდი და კომპონენტი არ იმპორტირებს `data/products.js`-ს.
ერთადერთი ფაილი, რომელიც `data/`-ს კითხულობს, არის `services/mockApi.js`.

`services/api.js`-ის კონტრაქტი:

| მეთოდი | აბრუნებს |
|---|---|
| `getProducts({ category, filters, sort, page, limit, q })` | `{ items, total, page, totalPages, limit, facets }` |
| `getProductBySlug(slug)` | `Product` ან `throws NotFoundError` |
| `getProductById(id)` | `Product` ან `throws NotFoundError` |
| `getRelatedProducts(id, limit)` | `Product[]` (იგივე კატეგორია, ფასის ±30%) |
| `getCategories()` | `Category[]` + `productsCount` |
| `getHomeSections()` | `{ newArrivals, discounted, featured, popularCategories }` |
| `searchProducts(q, limit)` | `Product[]` (autocomplete) |
| `createOrder(payload)` | `Order` (`orderNumber`-ით) |
| `getOrders()` / `getOrderByNumber(n)` | `Order[]` / `Order` |
| `login` / `register` / `logout` / `getProfile` / `updateProfile` / `changePassword` | სესია / `User` |
| `getAddresses` / `saveAddress` / `deleteAddress` | `Address[]` |

`mockApi` ყველა ფილტრს, სორტს და პაგინაციას **მეხსიერებაში** ამუშავებს და 200–400ms
ხელოვნურ დაყოვნებას იძენს, რომ loading-სთეითები რეალურ პირობებში გამოიცადოს.

წარმოებული (derived) ველები — `discountPercent`, `hasDiscount`, `inStock`,
`isLowStock` — mock მონაცემებში **არ იწერება**; მათ data layer ითვლის (`decorate()`).

### მდგომარეობის მართვა

| Context | პასუხისმგებლობა |
|---|---|
| `CartContext` | `useReducer` (`HYDRATE / ADD / REMOVE / SET_QTY / CLEAR`), `localStorage` სინქრონიზაცია, `useMemo` selector-ები |
| `AuthContext` | mock სესია, `initializing` / `pending` მდგომარეობები |
| `ToastContext` | შეტყობინებების რიგი, ქმედების ღილაკით (undo) |

ბიზნეს-ლოგიკა JSX-ში არ ცხოვრობს: ფილტრაცია/სორტი — `utils/filter.js`,
ძებნა — `utils/search.js`, ფასები — `utils/format.js` და `utils/pricing.js`.

---

## Backend-ზე გადასვლა

გადართვა ხდება **მხოლოდ `.env`-ით** — კოდის ცვლილების გარეშე:

```dotenv
# .env
VITE_API_MODE=http
VITE_API_BASE_URL=https://api.voltbox.ge
```

არჩევანი ხდება **ბილდის დროს**, არა runtime-ზე. `services/api.js` ერთადერთ
სპეციფიკატორს აიმპორტებს:

```js
import * as impl from 'virtual:api-impl';
```

რომელსაც `vite.config.js` კონკრეტულ ფაილად ხსნის:

```js
const envDir  = fileURLToPath(new URL('.', import.meta.url));   // = frontend/
const apiMode = loadEnv(mode, envDir, '').VITE_API_MODE === 'http' ? 'http' : 'mock';
const apiImpl = apiMode === 'http' ? './src/services/httpApi.js' : './src/services/mockApi.js';
// resolve.alias: { 'virtual:api-impl': <apiImpl-ის აბსოლუტური გზა> }
```

**რატომ alias და არა `if`:** ორივე მოდულის სტატიკური იმპორტისას გამოუყენებელი
იმპლემენტაცია მაინც ხვდება ბანდლში — Rollup `data/products.js`-ის მოდულის
დონეზე `.map()`-ს პოტენციურ side effect-ად თვლის და ვერ აგდებს. alias-ით კი
მოდულების გრაფში *მხოლოდ ერთი* ფაილი ხვდება. გაზომილი შედეგი:

| რეჟიმი | raw | gzip |
|---|---|---|
| `mock` | 405.7 KB | 121.0 KB |
| `http` (mock ბაზა გამორიცხულია) | **361.0 KB** | **107.5 KB** |

ანუ backend-ზე გადასვლისას 61-პროდუქტიანი mock ბაზა (~45 KB) ავტომატურად ქრება.

`services/httpApi.js` უკვე შეიცავს ყველა მეთოდს **იმავე ხელმოწერით**, `fetch`-ის
wrapper-ს (`request()`), ავტორიზაციის header-ს და შეცდომების ერთიან იერარქიას
(`ApiError` / `NotFoundError` / `ValidationError` / `AuthError`).
თითოეულ ფუნქციაზე მითითებულია მოსალოდნელი endpoint `// TODO: connect backend`
კომენტარით:

| ფუნქცია | Endpoint |
|---|---|
| `getProducts` | `GET /products?category=&sort=&page=&limit=&q=&<filters>` |
| `getProductBySlug` | `GET /products/:slug` |
| `getRelatedProducts` | `GET /products/:id/related?limit=` |
| `getCategories` | `GET /categories` |
| `getHomeSections` | `GET /home-sections` |
| `searchProducts` | `GET /search?q=&limit=` |
| `createOrder` | `POST /orders` |
| `getOrders` | `GET /orders` |
| `login` / `register` / `logout` | `POST /auth/login` / `/auth/register` / `/auth/logout` |
| `getProfile` / `updateProfile` | `GET` / `PATCH /auth/me` |
| `changePassword` | `POST /auth/change-password` |
| `getAddresses` / `saveAddress` / `deleteAddress` | `GET` / `POST`,`PUT` / `DELETE /addresses` |

**რა უნდა გააკეთოს backend-მა**, რომ UI-ს არაფერი შეეცვალოს:

1. `GET /products` დააბრუნოს `{ items, total, page, totalPages, limit, facets }`,
   სადაც `facets = { values: { "brand": { "Apple": 12 }, "specs.ram": { "8 GB": 5 } }, price: { min, max } }`.
   Facet-ის რაოდენობები უნდა ითვლებოდეს **ყველა სხვა ფილტრის** გათვალისწინებით
   (იმ ჯგუფის გარდა, რომელსაც ეხება) — ეს არის სტანდარტული e-commerce ქცევა.
2. პროდუქტში დააბრუნოს §[მონაცემთა კონტრაქტი](#მონაცემთა-კონტრაქტი)-ის ველები
   **პლუს** წარმოებულები (`discountPercent`, `hasDiscount`, `inStock`, `isLowStock`),
   ან დაუბრუნოს „ნედლი“ ველები და `httpApi.js`-ში დაემატოს იგივე `decorate()`.
3. ძებნა გადავიდეს სერვერზე — მაშინ `utils/search.js` მხოლოდ ერთ ადგილას წყვეტს
   გამოძახებას (`mockApi.js`), UI-ს არაფერი ეცვლება.

მოკლედ: **`.env` იცვლება — მეტი არაფერი.**

### Backend უკვე არსებობს

`backend/` საქაღალდეში აწყობილია FastAPI + PostgreSQL იმპლემენტაცია, რომელიც
ზემოთ აღწერილ კონტრაქტს ასრულებს. გაშვება:

```bash
cd ../backend
docker compose up -d db          # ლოკალური Postgres
cp .env.example .env             # DATABASE_URL და JWT_SECRET
python -m venv .venv && .venv/Scripts/python.exe -m pip install -e ".[dev]"
alembic upgrade head
python scripts/seed.py --structure-only   # კატეგორიები + ბრენდები (პროდუქტების გარეშე)
uvicorn app.main:app --reload    # → http://localhost:8000
```

შემდეგ frontend-ის `.env`-ში:

```dotenv
VITE_API_MODE=http
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

დეტალები — [`../backend/README.md`](../backend/README.md).

**გვერდითი ეფექტი:** `http` რეჟიმში mock ბაზა ბანდლში აღარ ხვდება —
315.7 KB → **269.0 KB** (gzip 101.2 → **86.9 KB**).

---

## პროექტის სტრუქტურა

ყველა გზა `frontend/`-ის მიმართ ფარდობითია.

```
index.html                       ← Vite-ის entry
vite.config.js                   ← alias, dev/preview სერვერები, envDir
tailwind.config.js               ← დიზაინ-ტოკენები
postcss.config.js
.env                             ← VITE_API_MODE (mock | http)
public/
├── favicon.svg
└── images/
    ├── placeholder.svg          ← ProductImage-ის fallback
    └── products/                ← 183 დაგენერირებული SVG (61 × 3)
scripts/
└── gen-images.mjs               ← სურათების გენერატორი
src/
├── components/
│   ├── layout/     Header, MobileMenu, Footer, Layout, Logo, UserMenu, RequireAuth,
│   │               ScrollToTop, PageFallback
│   ├── product/    ProductCard, ProductGrid, ProductCarousel, ProductGallery, RatingStars, PriceTag, StockBadge
│   ├── catalog/    FilterSidebar, FilterGroup, PriceRangeSlider, SortSelect, Pagination, ActiveFilters
│   ├── cart/       CartItem, CartSummary, CartBadge, QuantityStepper
│   ├── common/     Button, Input, Textarea, Select, Modal, Skeleton, EmptyState, ErrorState,
│   │               Breadcrumbs, Toast, Badge, ProductImage, CategoryIcon, ErrorBoundary
│   └── search/     SearchBar, SearchSuggestions
├── pages/          Home, Category, ProductDetails, Cart, Checkout, CheckoutSuccess,
│                   Login, Register, SearchResults, NotFound, Account/{AccountLayout,Orders,Profile,Addresses,ChangePassword}
├── context/        CartContext, AuthContext, ToastContext
├── hooks/          useCart, useAuth, useToast, useProducts, useDebounce,
│                   useLocalStorage, useRecentSearches, useQueryParams, useDocumentTitle
├── services/       api.js (კონტრაქტი), mockApi.js, httpApi.js, errors.js
├── data/           products.js (61), categories.js, brands.js
├── utils/          format.js, search.js, filter.js, pricing.js, storage.js, validate.js
├── constants/      index.js  ← ყველა განმეორებადი ტექსტი და კონფიგი
├── types.js        ← JSDoc @typedef-ები (Product, Category, Order, CartLine…)
├── App.jsx         ← მარშრუტები
└── main.jsx        ← providers + ErrorBoundary
```

### მარშრუტები

| გზა | გვერდი |
|---|---|
| `/` | Home |
| `/category/:slug` | Category (ფილტრები URL query-ში) |
| `/product/:slug` | ProductDetails |
| `/search?q=` | SearchResults |
| `/cart` | Cart |
| `/checkout` | Checkout (guest-ისთვისაც) |
| `/checkout/success/:id` | CheckoutSuccess |
| `/login`, `/register` | Auth |
| `/account/...` | Orders / Profile / Addresses / Password (protected → `/login?redirect=…`) |
| `*` | NotFound (404) |

---

## მონაცემთა კონტრაქტი

სრული ტიპები აღწერილია `src/types.js`-ში JSDoc `@typedef`-ებით (ავტოკომპლიტისთვის).

```js
{
  id: 'ph-001',
  slug: 'samsung-galaxy-s24-256gb',
  name: 'Samsung Galaxy S24 256GB',
  brand: 'Samsung',
  category: 'phones',                 // phones | cables | powerbanks | chargers | headphones | accessories
  shortDescription: '6.2" AMOLED, 8GB RAM, 5G',
  description: 'სრული აღწერა…',
  price: 2499,                        // number, GEL
  oldPrice: 2799,                     // number | null
  rating: 4.6,                        // 0–5
  reviewsCount: 128,
  stock: 12,                          // 0 = მარაგში არ არის
  isNew: true,
  isFeatured: true,
  images: ['/images/products/ph-001-1.svg', …],   // მინ. 3
  specs: { ram: '8 GB', storage: '256 GB', screen: '6.2"', network: '5G', color: 'შავი', … },
  tags: ['5g', 'amoled'],
  createdAt: '2026-07-14T10:00:00.000Z',
}
```

Mock ბაზა: **61 პროდუქტი** — 15 ტელეფონი, 12 კაბელი, 10 power bank, 8 დამტენი,
10 ყურსასმენი, 6 აქსესუარი. 20-ს აქვს `oldPrice`, 12-ს `isNew`, 10-ს `isFeatured`,
4-ს `stock: 0`.

---

## ახალი კატეგორიის დამატება

`FilterSidebar` **გენერიკულია** — ის კონკრეტულ კატეგორიაზე არაფერი იცის.
ახალი კატეგორიის დასამატებლად საკმარისია **ერთი ჩანაწერი** `src/data/categories.js`-ში:

```js
{
  id: 'speakers',
  name: 'დინამიკები',
  slug: 'speakers',
  icon: 'Speaker',                       // lucide-react-ის აიქონის სახელი
  description: 'პორტატული და სახლის აკუსტიკა.',
  filters: [
    { key: 'brand',            label: 'ბრენდი',      type: 'checkbox' },
    { key: 'specs.power',      label: 'სიმძლავრე',   type: 'checkbox' },
    { key: 'specs.waterproof', label: 'წყალგამძლე',  type: 'toggle', match: true },
    { key: 'specs.color',      label: 'ფერი',        type: 'swatch'   },
  ],
}
```

დამატებით მხოლოდ:
- `src/components/common/CategoryIcon.jsx` — ერთი ხაზი აიქონის რუკაში;
- `src/constants/index.js` → `SPEC_LABELS` — ახალი `specs` გასაღების ქართული ლეიბლი
  (და `COLOR_SWATCHES` — ახალი ფერი, თუ საჭიროა).

ფილტრების ტიპები:

| `type` | ქცევა |
|---|---|
| `checkbox` | მრავლობითი არჩევანი (OR ჯგუფის შიგნით, AND ჯგუფებს შორის) |
| `toggle` | ჩართვა/გამორთვა; `match` განსაზღვრავს „ჩართულის“ მნიშვნელობას (default `true`) |
| `swatch` | ფერების ბადე (`COLOR_SWATCHES`-იდან) |

არასავალდებულო ველები: `param` (URL-ის პარამეტრის სახელი, default — `key`-ის
ბოლო სეგმენტი) და `optionLabels` (ტექნიკური მნიშვნელობის ადამიანური სახელი).

**კომპონენტის დაწერა არ არის საჭირო.** Facet-ების დათვლა, ოფციების ბუნებრივი
დალაგება (`8 GB` < `12 GB` < `256 GB`), chip-ები და URL-სინქრონიზაცია ავტომატურია.

---

## ძებნის ალგორითმი

მთელი ლოგიკა იზოლირებულია `src/utils/search.js`-ში და გამოიძახება მხოლოდ
`mockApi.js`-იდან.

ძებნა მუშაობს ერთდროულად ველებზე: `name`, `brand`, `category` (ქართული სახელიც),
`specs` (ყველა მნიშვნელობა), `tags`, `shortDescription`, `description`.

**1. ნორმალიზაცია** (`normalize`, ველი-ველზე):
- lowercase, პუნქტუაცია → სივრცე, ზედმეტი space-ების მოცილება;
- ათასეულების გამყოფები: `20 000` → `20000`, `20,000` → `20000`;
- ერთეულების უნიფიკაცია: `mah / მაჰ`, `m / მ / მეტრი`, `sm / cm / სმ`, `gb / გბ`,
  `w / ვტ / ვატი`, `h / სთ / საათი`, `in` (`6.2"` → `6.2 in`);
- რიცხვისა და ერთეულის გამოყოფა: `20000mAh` → `20000 mah`, `2მ` → `2 m`.

**2. ტოკენიზაცია:** query იშლება სიტყვებად — **AND ტოკენებზე, OR ველებზე**.
ქართული მორფოლოგიისთვის გამოიყენება მსუბუქი სტემინგი
(`ყურსასმენები` ↔ `ყურსასმენი` → `ყურსასმენ`).
წმინდა რიცხვითი და 1–2-სიმბოლოიანი ტოკენები („2“, „c“, „m“, „5g“) მხოლოდ **ზუსტად**
ემთხვევა — თორემ „2“ დაემთხვეოდა „24 თვე“-ს, ხოლო „m“ — „mAh“-ს.

**3. რანჟირება:** `name` 10 > `brand` 6 > `category` 5 > `specs` 4 > `tags` 3 >
`shortDescription` 2 > `description` 1. ზუსტ დამთხვევას, პრეფიქსს და სახელში
სრული query-ს არსებობას ემატება ბონუსი; მარაგში მყოფი და მაღალრეიტინგული
პროდუქტები ოდნავ წინ იწევენ.

გამოცდილი ქეისები:

| Query | შედეგი |
|---|---|
| `20 000` | 4 × Power Bank 20 000 mAh |
| `USB C 2m` | 4 × USB-C კაბელი 2 მეტრი |
| `samsung 5g` | 4 × Samsung-ის 5G ტელეფონი |
| `უსადენო ყურსასმენი` | 8 × wireless headphones (სადენიანი გამორიცხულია) |

---

## URL-ის მდგომარეობა

ფილტრები, სორტი, გვერდი და ძებნის ტექსტი ცხოვრობს **მხოლოდ URL query params-ში**
(`hooks/useQueryParams.js`). გვერდის refresh-ის ან ბმულის გაზიარების შემდეგ
მდგომარეობა იდენტურად აღდგება.

```
/category/phones?brand=Apple,Samsung&ram=8+GB&price=1000-3000&network=1&sort=price_asc&page=2
```

| პარამეტრი | მნიშვნელობა |
|---|---|
| `<filter>` | ფილტრის `key`-ის ბოლო სეგმენტი; მნიშვნელობები მძიმით (`brand=Apple,Samsung`) |
| `price` | `min-max` (`price=100-500`) |
| toggle-ფილტრი | `1` (`network=1` = მხოლოდ 5G) |
| `sort` | `popular` (default, არ იწერება) / `newest` / `price_asc` / `price_desc` / `rating`; ძებნაზე default — `relevance` |
| `page` | > 1 შემთხვევაში |
| `q` | ძებნის ტექსტი |

---

## Bundle და code splitting

გვერდები იტვირთება მოთხოვნისამებრ: `App.jsx`-ში თითოეული მარშრუტი `React.lazy`-ია,
ხოლო `components/layout/Layout.jsx` მათ `<Suspense>`-ში ახვევს skeleton-fallback-ით
(`components/layout/PageFallback.jsx`). Vite თითოეულ გვერდს ცალკე chunk-ად ჭრის.

`Layout`, `Header`, `Footer`, context-ები და საერთო კომპონენტები **განზრახ რჩება**
მთავარ ბანდლში — ისინი ყველა მარშრუტზე საჭიროა და გაყოფა მხოლოდ დამატებით
მოთხოვნებს დაამატებდა.

გაზომილი payload მარშრუტების მიხედვით (JS, gzip; საწყისი ერთი chunk — 121.9 KB):

| მარშრუტი | gzip | სხვაობა | ფაილი |
|---|---|---|---|
| `/login` | 102.6 KB | −15.8% | 5 |
| `/cart` | 105.2 KB | −13.7% | 11 |
| `/` | 106.5 KB | −12.6% | 10 |
| `/checkout` | 107.9 KB | −11.4% | 12 |
| `/product/:slug` | 111.1 KB | −8.8% | 15 |
| `/category/:slug` | 111.3 KB | −8.6% | 13 |

**რატომ არა მეტი:** `react-dom` + `react-router` = ბანდლის 41% და ისინი ყოველთვის
საჭიროა; `data/products.js` კიდევ 15%-ია და mock რეჟიმში ყველა გვერდს სჭირდება.
lazy-ის სამიზნე `pages/` მთლიანის 14%-ია. `http` რეჟიმში ორივე ოპტიმიზაცია ჯამდება
და მთავარი ბანდლი 312 KB-მდე ეცემა.

```bash
npx vite build --manifest   # dist/.vite/manifest.json — chunk-ების გრაფი
```

---

## დიზაინ-ტოკენები

პალიტრა და ტიპოგრაფია განსაზღვრულია `tailwind.config.js`-ში — Tailwind-ის
ნაგულისხმევი `blue-500` არსად არ გამოიყენება.

| ტოკენი | დანიშნულება |
|---|---|
| `primary` (50–950, `#2440e0`) | ბრენდის ლურჯი — CTA, ბმულები, focus-ring, აქტიური მდგომარეობები |
| `accent` (50–900, `#ff7f11`) | „volt“ ნარინჯისფერი — ფასდაკლებები, ბეჯები, ვარსკვლავები |
| `ink` (50–950) | ნეიტრალური ტექსტი და ზედაპირები |
| `success` / `danger` / `warning` | სტატუსები |

დამატებით: `rounded-card` / `rounded-control` / `rounded-pill`,
`shadow-card` / `shadow-card-hover` / `shadow-popover`,
ანიმაციები `badge-pop`, `slide-up`, `sheet-up`, `slide-in-left/right`, `shimmer`.
Spacing ეყრდნობა Tailwind-ის 4px ბადეს.

Breakpoints: `sm 640 / md 768 / lg 1024 / xl 1280`. მაკეტი გამართულია 360px-იდან
1920px-მდე (grid: mobile 2 / tablet 3 / desktop 4 სვეტი).

### Accessibility

სემანტიკური ტეგები, `alt` ყველა სურათზე, `aria-label` აიქონ-ღილაკებზე, ხილული
focus-ring, keyboard trap მოდალებში (`Esc` + ფოკუსის დაბრუნება), `role="combobox"`
ძებნაზე ↑ ↓ Enter Esc ნავიგაციით, `aria-live` შედეგების მრიცხველზე,
skip-link მთავარ კონტენტზე და `prefers-reduced-motion` მხარდაჭერა.

**კონტრასტი — გაზომილი, არა სავარაუდო.** პალიტრის 17 კრიტიკული წყვილი შემოწმდა
WCAG 2.1 AA-ზე (≥ 4.5:1 ტექსტისთვის, ≥ 3:1 UI-ელემენტებისთვის):

| მდგომარეობა | ტოკენები | კონტრასტი |
|---|---|---|
| სხეულის ტექსტი | `ink-900` / თეთრი | 15.69:1 |
| მეორეხარისხოვანი ტექსტი | `ink-600` / თეთრი | 6.20:1 |
| hint-ტექსტი, facet-ების რიცხვები, ძველი ფასი | `ink-500` / თეთრი | 4.98:1 |
| hint-ტექსტი გვერდის ფონზე | `ink-500` / `ink-50` | 4.69:1 |
| ბმულები და აქტიური ნავიგაცია | `primary-700` / თეთრი | 9.28:1 |
| მთავარი CTA | თეთრი / `primary-600` | 7.28:1 |
| ფასდაკლების და კალათის ბეჯი | თეთრი / `accent-600` | 4.93:1 |
| „ბოლო ცალები“ | `warning-600` / `warning-50` | 4.73:1 |
| „მარაგშია“ | `success-700` / `success-50` | 5.21:1 |
| შეცდომის ტექსტი | `danger-600` / თეთრი | 4.83:1 |

`ink-400` შენარჩუნებულია მხოლოდ იქ, სადაც WCAG კონტრასტს არ მოითხოვს:
გამორთულ (`disabled`) კონტროლებზე და `aria-hidden` დეკორატიულ აიქონებზე.
`accent-500` (`#ff7f11`) დარჩა დეკორატიულ როლში — hero-ს გრადიენტსა და
რეიტინგის ვარსკვლავებზე; ტექსტის ფონად გამოიყენება `accent-600` (`#c74407`).

---

## localStorage

| გასაღები | შიგთავსი |
|---|---|
| `cart:v1` | კალათის ჩანაწერები `snapshot`-ით (ფასი/სახელი/მარაგი დამატების მომენტში) |
| `auth:v1` | მიმდინარე სესია (`{ user, token }`) |
| `users:v1` | დარეგისტრირებული მომხმარებლები — **MOCK ONLY** |
| `orders:v1` | გაფორმებული შეკვეთები |
| `addresses:v1` | შენახული მისამართები |
| `recent-searches:v1` | ბოლო 5 ძებნა (SearchBar-ის ჩამოსაშლელი) |

ყველა წვდომა გადის `utils/storage.js`-ზე: `try/catch`, გატეხილი JSON-ის უსაფრთხო
დამუშავება (ჩანაწერი იშლება), private mode-ის მხარდაჭერა და `storage` event-ით
სხვა tab-თან სინქრონიზაცია.

> ⚠️ ავტორიზაცია **mock-ია**: პაროლები ინახება მხოლოდ base64-ით დაფარულად და
> არავითარ უსაფრთხოებას არ უზრუნველყოფს. შესაბამის ფაილებში დატანილია
> `// MOCK ONLY — replace with real auth API` კომენტარი.
> კალათა და შეკვეთა ავტორიზაციის გარეშე მუშაობს.

---

## ვარაუდები

პროექტის მსვლელობისას მიღებული გადაწყვეტილებები აღწერილია
[`ASSUMPTIONS.md`](./ASSUMPTIONS.md)-ში.

რაც განზრახ გადავდეთ — გაზომილ საბაზისო მაჩვენებლებთან და კოდში შესვლის
წერტილებთან ერთად — [`ROADMAP.md`](./ROADMAP.md)-შია.
