# ROADMAP — რა დარჩა მომავლისთვის

ეს ფაილი ინახავს იმას, რაზეც ვისაუბრეთ, მაგრამ განზრახ გადავდეთ.
თითოეულ პუნქტთან მითითებულია **საიდან დაიწყო** — რომ კონტექსტის აღდგენა
ნულიდან არ დაგჭირდეს.

> სტატუსი: საწყისი ტექნიკური დავალება **სრულად დახურულია** (8/8 მიღების
> კრიტერიუმი). ქვემოთ ჩამოთვლილი არცერთი პუნქტი არ არის მოთხოვნილი —
> ყველა გაუმჯობესებაა.

---

## 🔴 P0 — ეს დღესვე ღირს

### 1. Git

პროექტი ვერსიების კონტროლის გარეშეა. დაგროვდა **ხუთი** სერიოზული ცვლილება
(WCAG პალიტრა, `virtual:api-impl` alias, code splitting, ფორმატირების ფუნქციები,
ბოლო ძებნები) — უკან დაბრუნების საშუალების გარეშე.

```bash
git init
git add .
git commit -m "VoltBox frontend — mock data layer, WCAG AA palette, code splitting"
```

`.gitignore` უკვე გამზადებულია (`node_modules`, `dist`, `.env.local`).
`.env` განზრახ **არ** არის იგნორირებული — მასში საიდუმლო არაფერია და
გადამრთველად გვჭირდება.

---

## 🟠 P1 — უახლოესი ნაბიჯები

### 0. monorepo-ს გასწორება: `src/` → `frontend/`  ·  ~30 წთ

**პრობლემა:** backend სუფთად არის ჩაკეტილი `backend/`-ში, frontend კი repo-ს
ძირშია გაფანტული (`src/`, `public/`, `index.html`, `package.json`,
`vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `.env`). ორი
თანაბარმნიშვნელოვანი ნაწილი სხვადასხვა დონეზეა.

**სასურველი სახე:**

```
voltbox/
├── frontend/     src, public, package.json, vite.config…
├── backend/      app, alembic, pyproject.toml…
├── README.md  ASSUMPTIONS.md  ROADMAP.md
└── .github/
```

**შესაცვლელი 5 ადგილი** (`git mv`-ით ისტორია შენარჩუნდება):

| ფაილი | რა |
|---|---|
| `backend/scripts/export_mock_data.mjs` | `../../src/data/` → `../../frontend/src/data/` |
| `.github/workflows/backend.yml` | `paths:` და `working-directory` |
| `.github/workflows/` (frontend) | ახალი workflow ან paths |
| `README.md`, `backend/README.md` | ბმულები და გზები |
| `.gitignore` | `backend/.env` გვერდით `frontend/.env` |

**რატომ ახლა და არა მოგვიანებით:** deploy-ის კონფიგურაცია (Netlify/Vercel base
directory) ჯერ არ არსებობს. მისი დაყენების შემდეგ გასწორება ხუთის ნაცვლად
შვიდ ადგილს შეეხება.

**შემოწმება:** 110 backend-ტესტი + `npm run build` + jsdom E2E — ყველაფერი
დაფარულია, გატეხვა მაშინვე გამოჩნდება.

**ყველაზე რეალური დაბნეულობა დღეს:** ორი `.env` — `./.env` (Vite) და
`backend/.env` (FastAPI), სხვადასხვა შიგთავსით.


### 2. SEO / share preview  ·  ~40 წთ

**პრობლემა:** `index.html`-ში **0** Open Graph ტეგია. ბმულს უკვე უზიარებ
სხვებს, მაგრამ WhatsApp/Facebook preview-ს ვერ აჩვენებს — არც სათაური,
არც სურათი, არც აღწერა.

**რა უნდა გაკეთდეს:**
- `index.html` — სტატიკური `og:title`, `og:description`, `og:image`, `og:type`,
  `twitter:card`
- პროდუქტის გვერდზე დინამიური ტეგები (`useDocumentTitle`-ის გვერდით ახალი
  `useMeta` hook, ან `react-helmet-async`)
- `application/ld+json` — `Product` schema (`name`, `image`, `offers.price`,
  `aggregateRating`) → Google-ის rich snippet

**გასათვალისწინებელი:** SPA-ს og-ტეგებს კრაულერების ნაწილი ვერ კითხულობს
(JS არ ეშვება). სრული გადაწყვეტა prerender-ია (`vite-plugin-ssg`) — ეს უკვე
დიდი ცვლილებაა და დავალების non-goal-ში (SSR) ხვდება.

**შესვლის წერტილი:** [index.html](index.html), [src/hooks/useDocumentTitle.js](src/hooks/useDocumentTitle.js)

### 3. Vitest — ტესტები  ·  ~1 სთ

`utils/search.js` და `utils/filter.js` სუფთა ფუნქციებია. ის **4 ტესტ-ქეისი**
(`20 000`, `USB C 2m`, `samsung 5g`, `უსადენო ყურსასმენი`), რომელსაც ხელით
ვამოწმებდით, ავტომატური უნდა გახდეს — თორემ მომდევნო ცვლილებაზე ჩუმად გატყდება.

**რა დაიფაროს პირველ რიგში:**
- `normalize()` — ერთეულები, ათასეულების გამყოფები, ინჩის ნიშანი
- `searchProducts()` — 4 სავალდებულო ქეისი + „მოკლე ტოკენი ზუსტად ემთხვევა“
- `computeFacets()` — რაოდენობა სხვა ფილტრების გათვალისწინებით
- `calcTotals()` / `calcShipping()` — 150 ₾-ის ზღვარი
- `cartReducer` — qty clamp, დუბლიკატის აცილება, გატეხილი JSON

**გასათვალისწინებელი:** `services/api.js` სუფთა Node-ით არ იხსნება
(`virtual:api-impl` alias) — Vitest-ის კონფიგში იგივე alias უნდა გამეორდეს,
ან ტესტებმა პირდაპირ `mockApi.js` აიღონ.

**შესვლის წერტილი:** [src/utils/search.js](src/utils/search.js), [ASSUMPTIONS.md](ASSUMPTIONS.md) §3

### 4. ESLint + Prettier  ·  ~30 წთ

ახლა არცერთი არ არის. სამუშაოს განმავლობაში ხელით ვიჭერდი გამოუყენებელ
იმპორტებს — ეს ავტომატური უნდა იყოს.

რეკომენდებული: `eslint-plugin-react-hooks` (deps-ის შემოწმება),
`eslint-plugin-jsx-a11y` (a11y რეგრესიები), `lint-staged` + `husky`.

---

## 🟡 P2 — ფუნქციები, რომლებსაც მაღაზია მოელის

### 5. რჩეულები (wishlist)  ·  ~1.5 სთ

ყველაზე ხშირად მოთხოვნადი დანაკლისი. ინფრასტრუქტურა მზადაა — კალათის
`snapshot` პატერნი პირდაპირ ჯდება.

- `context/WishlistContext.jsx` (ან `hooks/useWishlist.js` `useLocalStorage`-ზე,
  როგორც `useRecentSearches` გაკეთდა)
- გულის აიქონი `ProductCard`-ზე და `ProductDetails`-ზე
- `/account/wishlist` გვერდი
- `STORAGE_KEYS.wishlist = 'wishlist:v1'`

**შესვლის წერტილი:** [src/hooks/useRecentSearches.js](src/hooks/useRecentSearches.js) — იგივე ნიმუში

### 6. ბოლოს ნანახი პროდუქტები  ·  ~45 წთ

`ProductDetails`-ის mount-ზე ინახება `snapshot`; ჩანს მთავარ გვერდზე და
პროდუქტის გვერდის ბოლოს („მსგავსი პროდუქტების“ გვერდით).

### 7. შეფასებების UI  ·  ~2 სთ

`rating` და `reviewsCount` მონაცემებში **გვაქვს**, მაგრამ UI არ არსებობს:
- შეფასებების სია (ავტორი, თარიღი, ტექსტი, ვარსკვლავები)
- განაწილების დიაგრამა (5★ — 60%, 4★ — 25%…)
- დაწერის ფორმა (mock, `localStorage`)
- `mockApi`-ს დასჭირდება `getReviews(productId)` + `createReview()`

### 8. პროდუქტების შედარება  ·  ~2 სთ

`specs`-ის სტრუქტურა უკვე იდეალურია გვერდიგვერდ ცხრილისთვის.
`SPEC_LABELS` ლეიბლებს უკვე თარგმნის.

### 9. პრომო-კოდი checkout-ზე  ·  ~45 წთ

`utils/pricing.js`-ის `calcTotals()` ერთი პარამეტრით ფართოვდება
(`discountCode`). ვალიდაცია — `mockApi`-ში.

### 10. მიწოდების თარიღი + შეკვეთის სტატუსის timeline  ·  ~1 სთ

`Order.status` უკვე არსებობს (`pending / processing / shipped / delivered`),
მაგრამ `/account/orders`-ზე მხოლოდ ბეჯად ჩანს. timeline უფრო თვალსაჩინოა.

### 11. `Cmd / Ctrl + K` ძებნის გასახსნელად  ·  ~20 წთ

`SearchBar`-ს კლავიატურის სრული მხარდაჭერა **უკვე აქვს** (↑ ↓ Enter Esc) —
მხოლოდ გლობალური hotkey აკლია.

---

## 🟢 P3 — სასიამოვნო, მაგრამ არასავალდებულო

### 12. Deploy — მუდმივი ბმული

ngrok-ის URL ყოველ გაშვებაზე იცვლება და კომპიუტერის გამორთვაზე კვდება.
`dist/` პირდაპირ Netlify/Vercel-ზე (drag & drop-იც მუშაობს).

SPA-სთვის საჭიროა fallback: Netlify → `public/_redirects` ფაილში
`/*  /index.html  200`; Vercel → `vercel.json`-ის `rewrites`.

### 13. Dark mode

პალიტრა უკვე ტოკენიზებულია (`primary` / `accent` / `ink` სკალები), ამიტომ
`dark:` ვარიანტების დამატება მექანიკური სამუშაოა. **გასათვალისწინებელი:**
კონტრასტი თავიდან უნდა გაიზომოს — ღია თემის 17 წყვილი მუქზე არ გადადის.

### 14. Prefetch on hover

გვერდის chunk-ები 1–11 KB-ია (gzip) და ლოკალურ ქსელზე მყისიერად იტვირთება.
ჰოვერზე წინასწარი ჩატვირთვა აზრს იძენს მხოლოდ მაშინ, თუ chunk-ები გაიზრდება.
იხ. [ASSUMPTIONS.md](ASSUMPTIONS.md) §6.4

### 15. ფასდაკლების ბეჯის ალტერნატიული ვარიანტი

კონტრასტის გასწორებისას ბეჯი ღია ნარინჯისფრიდან (`#ff7f11`) დამწვარზე
(`accent-600` = `#c74407`) გადავიდა — WCAG-ის მოთხოვნით.

თუ ეს ძალიან მუქად მოგეჩვენება, არსებობს **ვარიანტი B**: კაშკაშა ფონი
რჩება, ტექსტი მუქდება — `ink-900` `accent-500`-ზე = **6.20:1** (უფრო მაღალი
კონტრასტიც კი). ცვლილება — 5 წუთი, [Badge.jsx](src/components/common/Badge.jsx) `discount` ტონი.

### 16. i18n

ტექსტები უკვე თავმოყრილია [constants/index.js](src/constants/index.js)-ში
(`TEXT`, `SPEC_LABELS`, `HOME_SECTION_TITLES`, `DELIVERY_INFO`), ამიტომ
ლექსიკონად გადაქცევა კომპონენტების შეხების გარეშე შეიძლება.

---

## 📊 გაზომილი საბაზისო მაჩვენებლები

ეს ციფრები იმისთვისაა, რომ მომავალი ცვლილება შედარებადი იყოს.
გაზომვის თარიღი — 2026-09-09.

### Bundle (mock რეჟიმი, gzip)

| მარშრუტი | JS gzip |
|---|---|
| `/login` | 102.6 KB |
| `/cart` | 105.2 KB |
| `/` | 106.5 KB |
| `/checkout` | 107.9 KB |
| `/product/:slug` | 111.1 KB |
| `/category/:slug` | 111.3 KB |
| CSS (საერთო) | 8.1 KB |

`http` რეჟიმში mock ბაზა ბანდლში არ ხვდება: **361 KB raw / 107.5 KB gzip**
(mock რეჟიმში — 406 / 121).

```bash
npx vite build --manifest   # dist/.vite/manifest.json — chunk-ების გრაფი
```

### კონტრასტი

17 კრიტიკული წყვილი, ყველა ≥ 4.5:1 (WCAG AA). ყველაზე დაბალი —
`warning-600` / `warning-50` = **4.73:1**. სრული ცხრილი — [README.md](README.md) §Accessibility.

⚠️ პალიტრის ნებისმიერი ცვლილების შემდეგ კონტრასტი ხელახლა უნდა გაიზომოს.

### ბანდლის შემადგენლობა

| | წილი |
|---|---|
| react-dom | 27% |
| `data/products.js` | 15% |
| `components/` | 15% |
| `pages/` | 14% |
| react-router | 14% |
| utils / services / context | 10% |

React + Router = **41%** და ყოველთვის ჩამოდის — ამიტომ code splitting-ის
ჭერი ~15%-ია.

---

## ⚠️ რაც უნდა გახსოვდეს კოდში შესვლისას

**1. `virtual:api-impl` სუფთა Node-ით არ იხსნება.**
[api.js](src/services/api.js) იმპლემენტაციას ბილდის დროს ირჩევს
([vite.config.js](vite.config.js)-ის `resolve.alias`). ტესტ-სკრიპტებში ან
Vitest-ში იგივე alias ხელით უნდა გადაეცეს. მიზეზი — [ASSUMPTIONS.md](ASSUMPTIONS.md) §6.1.

**2. `api.js`-ში რეჟიმის შემოწმებას გამოთვლა არ უნდა დაემატოს.**
`?.`, `|| 'mock'` ან `.toLowerCase()` ლიტერალის დაკეცვას აფერხებს — ეს იყო
თავდაპირველი ხარვეზი, რომლის გამოც mock ბაზა `http` ბილდშიც ხვდებოდა.

**3. UI არასდროს არ იმპორტირებს `data/`-ს.**
მხოლოდ `services/mockApi.js`. ბრენდის ინფოც ამიტომ ერთვის პროდუქტს
data layer-ში (`brandCountry`), და არა კომპონენტში.

**4. Header `SearchBar`-ს ორჯერ ირენდერებს** (desktop + mobile).
ნებისმიერი ახალი `localStorage`-state იმავე პრობლემას შეეჯახება, რაც ბოლო
ძებნებს — ჩაწერამდე storage-ის ხელახლა წაკითხვა საჭიროა.
იხ. [hooks/useRecentSearches.js](src/hooks/useRecentSearches.js).

**5. ახალი კატეგორიის დამატება კომპონენტს არ საჭიროებს** — მხოლოდ ჩანაწერი
[data/categories.js](src/data/categories.js)-ში + აიქონი
[CategoryIcon.jsx](src/components/common/CategoryIcon.jsx)-ში.

---

## 🚀 როგორ გავუშვათ და გავუზიაროთ

```bash
npm install
npm run dev            # ლოკალური მუშაობა → localhost:5173

# სხვისთვის ჩვენება (ngrok უკვე გაწყობილია)
npm run preview:share  # ბილდი + preview → localhost:4173
ngrok http 4173        # საჯარო ბმული (URL ყოველ ჯერზე იცვლება)
```

`npm run dev:share` — dev-სერვერი ტუნელისთვის მორგებული HMR-ით (ცოცხალი
რედაქტირება გაზიარებისას). ngrok-ის ლოკალური პანელი — http://127.0.0.1:4040
