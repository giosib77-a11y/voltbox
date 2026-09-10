# ROADMAP — რა დარჩა მომავლისთვის

ეს ფაილი ინახავს იმას, რაზეც ვისაუბრეთ, მაგრამ განზრახ გადავდეთ.
თითოეულ პუნქტთან მითითებულია **საიდან დაიწყო** — რომ კონტექსტის აღდგენა
ნულიდან არ დაგჭირდეს.

> სტატუსი: საწყისი ტექნიკური დავალება **სრულად დახურულია** (8/8 მიღების
> კრიტერიუმი). ქვემოთ ჩამოთვლილი არცერთი პუნქტი არ არის მოთხოვნილი —
> ყველა გაუმჯობესებაა.

---

## ✅ დახურული

### ~~1. Git~~  ·  ✅ შესრულებულია

`github.com/giosib77-a11y/voltbox`, branch `main`.

`frontend/.env` განზრახ **არ** არის იგნორირებული — მასში საიდუმლო არაფერია და
გადამრთველად გვჭირდება. `backend/.env` კი იგნორირებულია — შეიცავს ბაზის
პაროლს და `JWT_SECRET`-ს.

---

### ~~0. monorepo-ს გასწორება: `src/` → `frontend/`~~  ·  ✅ შესრულებულია (2026-09-10)

frontend repo-ს ძირიდან `frontend/`-ში გადავიდა `git mv`-ით — ისტორია
შენარჩუნებულია. სამუშაო ხე ახლა:

```
voltbox/
├── frontend/   src, public, scripts, index.html, package.json, vite.config.js, .env
├── backend/    app, alembic, scripts, tests, pyproject.toml, .env
├── .github/workflows/   frontend.yml + backend.yml
└── README.md  ASSUMPTIONS.md  ROADMAP.md
```

**რა შეიცვალა კოდში:**

| ფაილი | ცვლილება |
|---|---|
| `backend/scripts/export_mock_data.mjs` | `../../src/data/` → `../../frontend/src/data/` |
| `frontend/vite.config.js` | `loadEnv(mode, process.cwd())` → `envDir` (კონფიგის საკუთარი დირექტორია) |
| `.gitignore` | გზები `frontend/`-ითა და `backend/`-ით პრეფიქსირებული |
| `.github/workflows/frontend.yml` | ახალი — `npm ci` + ბილდი matrix-ით (`mock` \| `http`) |
| `README.md` | გაიყო: ძირში monorepo-ს მიმოხილვა, დეტალები `frontend/README.md`-ში |
| `ASSUMPTIONS.md` | ახალი §9 — რატომ ასეა განლაგებული |

`frontend/vite.config.js`-ის relative გზები (`./src`, `./index.html`) კონფიგის
ფაილის მიმართაა და მასთან ერთად გადავიდა — შესწორება არ დასჭირდა.

დეტალები: [ASSUMPTIONS.md §9](./ASSUMPTIONS.md).


---

## 🟠 P1 — უახლოესი ნაბიჯები

### 1a. `/auth/refresh` — ტოკენის განახლება  ·  ~40 წთ

**პრობლემა:** backend-ს refresh-ტოკენის სრული როტაცია აქვს (`POST /auth/refresh`,
SHA-256-ით დაჰეშილი შენახვა, ერთჯერადი გამოყენება). frontend მას **არასოდეს
იძახებს** — `refreshToken` მხოლოდ logout-ზე იგზავნება.

```
ACCESS_TOKEN_TTL_MINUTES=30      ← ამის შემდეგ ყველა დაცული მოთხოვნა 401-ია
REFRESH_TOKEN_TTL_DAYS=30        ← ეს კი ჯიბეშია და გამოუყენებელი
```

**სიმპტომი:** 30 წუთის შემდეგ header კვლავ „შესულს“ აჩვენებს, `/account/*` კი
შეცდომას აგდებს. `AuthError` `services/`-ის გარეთ არსად არ იჭერს, ამიტომ სესია
არც სუფთად იხურება — შუალედური, გაუგებარი მდგომარეობა რჩება.

**რა უნდა გაკეთდეს:** `httpApi.js`-ის `request()`-ში 401-ზე ერთხელ სცადოს
`/auth/refresh`, ახალი ტოკენით გაიმეოროს მოთხოვნა, ჩავარდნაზე კი სესია სუფთად
დახუროს. პარალელური 401-ები ერთ refresh-ზე უნდა დაელოდონ (single-flight),
თორემ როტაცია ერთმანეთს გააუქმებს.

**შესვლის წერტილი:** [httpApi.js:48](frontend/src/services/httpApi.js#L48)
`request()`, [AuthContext.jsx](frontend/src/context/AuthContext.jsx).


### 1b. `Idempotency-Key` checkout-ზე  ·  ~15 წთ

**პრობლემა:** backend-ს `orders.idempotency_key` უნიკალური სვეტი და header-ის
პარამეტრი აქვს — ორჯერ გაგზავნილი შეკვეთა იმავე პასუხს აბრუნებს. frontend
header-ს **არ აგზავნის**, ანუ დაცვა ჩართული არასოდესაა.

**სიმპტომი:** ნელ კავშირზე „შეკვეთის გაფორმებაზე“ ორჯერ დაჭერა ორ შეკვეთას ქმნის
და მარაგს ორჯერ ჭამს.

**რა უნდა გაკეთდეს:** `createOrder`-ში `crypto.randomUUID()` კალათის სესიაზე
ერთხელ დაგენერირდეს (არა ყოველ ცდაზე — თორემ აზრი ეკარგება) და header-ად წავიდეს.

**შესვლის წერტილი:** [httpApi.js](frontend/src/services/httpApi.js) `createOrder`,
[orders.py:62](backend/app/api/v1/routes/orders.py#L62).


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

**შესვლის წერტილი:** [index.html](frontend/index.html), [src/hooks/useDocumentTitle.js](frontend/src/hooks/useDocumentTitle.js)

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

**შესვლის წერტილი:** [src/utils/search.js](frontend/src/utils/search.js), [ASSUMPTIONS.md](ASSUMPTIONS.md) §3

### 4. ESLint + Prettier  ·  ~30 წთ

ახლა არცერთი არ არის. სამუშაოს განმავლობაში ხელით ვიჭერდი გამოუყენებელ
იმპორტებს — ეს ავტომატური უნდა იყოს.

რეკომენდებული: `eslint-plugin-react-hooks` (deps-ის შემოწმება),
`eslint-plugin-jsx-a11y` (a11y რეგრესიები), `lint-staged` + `husky`.

---

### 4a. ადმინ პანელი — რა სჭირდება backend-ისგან

**გადაწყვეტილი:** პროდუქტები ხელით ადმინ პანელიდან შეიყვანება და პირდაპირ
ბაზაში აისახება. მანამდე ერთადერთი გზა `scripts/import_products.py`-ია.

**რაც უკვე მზადაა:**
- `users.role` სვეტი ბაზაშია (`server_default="customer"`) — მიგრაცია არ სჭირდება
- `import_products.py`-ში ვალიდაციისა და `search_text`-ის გამოთვლის ლოგიკა
  უკვე დაწერილია — endpoint-ებმა იგივე უნდა გამოიყენონ, არა თავისი ასლი

**რაც არ არსებობს:**

| | დღეს | სჭირდება |
|---|---|---|
| კატალოგზე ჩაწერა | **არცერთი endpoint** — API წასაკითხია | `POST/PATCH/DELETE` პროდუქტზე, კატეგორიაზე, ბრენდზე |
| `role`-ის შემოწმება | სვეტი არსებობს, არსად არ იკითხება | `require_admin` დამოკიდებულება |
| სურათების ატვირთვა | `SUPABASE_PROJECT_REF` / `SERVICE_ROLE_KEY` `.env`-შია, ცარიელი | Supabase Storage-ის კავშირი |

**⚠️ ორი ხაფანგი, რომელიც ხელით ჩაწერისას ყველაზე ხშირად ტყდება:**

1. **`search_text`** — თუ endpoint-მა არ გამოთვალა, პროდუქტი კატალოგში გამოჩნდება,
   ძებნა კი ვერ იპოვის. ჩუმი ხარვეზია. `scripts/reindex_search.py` ასწორებს,
   მაგრამ ჯობია endpoint-მა თავიდანვე სწორად ჩაწეროს.
2. **`is_primary` / `position` სურათებზე** — ერთი და მხოლოდ ერთი მთავარი სურათი
   უნდა იყოს (ბაზაში partial unique index იცავს — არასწორი ჩაწერა
   `IntegrityError`-ით ჩავარდება, არა ჩუმად).

**შენიშვნა:** საწყისი ტექნიკური დავალების §13-ით ადმინ პანელი განზრახ scope-ს
გარეთაა. აქ მხოლოდ იმის ჩამონათვალია, რაც backend-ს დასჭირდება.


## 🟡 P2 — ფუნქციები, რომლებსაც მაღაზია მოელის

### 5. რჩეულები (wishlist)  ·  ~1.5 სთ

ყველაზე ხშირად მოთხოვნადი დანაკლისი. ინფრასტრუქტურა მზადაა — კალათის
`snapshot` პატერნი პირდაპირ ჯდება.

- `context/WishlistContext.jsx` (ან `hooks/useWishlist.js` `useLocalStorage`-ზე,
  როგორც `useRecentSearches` გაკეთდა)
- გულის აიქონი `ProductCard`-ზე და `ProductDetails`-ზე
- `/account/wishlist` გვერდი
- `STORAGE_KEYS.wishlist = 'wishlist:v1'`

**შესვლის წერტილი:** [src/hooks/useRecentSearches.js](frontend/src/hooks/useRecentSearches.js) — იგივე ნიმუში

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
კონტრასტიც კი). ცვლილება — 5 წუთი, [Badge.jsx](frontend/src/components/common/Badge.jsx) `discount` ტონი.

### 16. i18n

ტექსტები უკვე თავმოყრილია [constants/index.js](frontend/src/constants/index.js)-ში
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
[api.js](frontend/src/services/api.js) იმპლემენტაციას ბილდის დროს ირჩევს
([vite.config.js](frontend/vite.config.js)-ის `resolve.alias`). ტესტ-სკრიპტებში ან
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
იხ. [hooks/useRecentSearches.js](frontend/src/hooks/useRecentSearches.js).

**5. ახალი კატეგორიის დამატება კომპონენტს არ საჭიროებს** — მხოლოდ ჩანაწერი
[data/categories.js](frontend/src/data/categories.js)-ში + აიქონი
[CategoryIcon.jsx](frontend/src/components/common/CategoryIcon.jsx)-ში.

---

## 🚀 როგორ გავუშვათ და გავუზიაროთ

```bash
cd frontend
npm install
npm run dev            # ლოკალური მუშაობა → localhost:5173

# სხვისთვის ჩვენება (ngrok უკვე გაწყობილია)
npm run preview:share  # ბილდი + preview → localhost:4173
ngrok http 4173        # საჯარო ბმული (URL ყოველ ჯერზე იცვლება)
```

`npm run dev:share` — dev-სერვერი ტუნელისთვის მორგებული HMR-ით (ცოცხალი
რედაქტირება გაზიარებისას). ngrok-ის ლოკალური პანელი — http://127.0.0.1:4040
