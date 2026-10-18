# VoltBox — DESIGN.md

წყარო: არსებული კოდი (`frontend/tailwind.config.js`, `src/index.css`, `src/fonts.css`, `src/components/**`, `src/admin/**`). ახალი სტილი არ არის შემოტანილი; მნიშვნელობები გადმოტანილია ზუსტად. `(დამატებულია)` = კოდში არ არის, ჩემი მინიმალური შევსება. `(ვერ დადგინდა)` = ვერ დავადგინე.

## 1. მიმართულება
ტექნიკის მაღაზია: სუფთა, ნეიტრალური ცივი-ნაცრისფერი (ink) ზედაპირები, ერთი ლურჯი `primary` ინტერაქციისთვის, ნარინჯისფერი `accent` — storefront-ზე მხოლოდ ფასს/ფასდაკლებას. Storefront-ს აქვს light და dark თემა; ადმინ-პანელი "გაყინულია" და ყოველთვის light-ია. ვერიდებით ფერის ერთადერთ სიგნალად გამოყენებას (სტატუსი = ტექსტი + ფერი) და `dark:` კლასებს (თემა = პალიტრის ცვლადები).

## 2. ფერები
Tailwind-ში ფერი როლით იწოდება და CSS ცვლადზე (`--c-<name>-<step>`) იხსნება. თემა: `:root` = admin; `html.theme-light` / `html.theme-dark` = storefront; `[data-admin]` (და `:root:has([data-admin])`) აბრუნებს admin-ს. ქვემოთ მნიშვნელობები **admin / storefront-light**, dark — ცალკე სვეტში, სადაც განსხვავდება. ნაბიჯის როლი ყველა თემაში ერთია.

| როლი (კლასი) | admin | light | dark |
|---|---|---|---|
| გვერდის ფონი `canvas`=ink-50 | #f7f8fa | იგივე | #171b23 |
| ზედაპირი `surface` (ბარათი, input, მოდალი) | #ffffff | იგივე | #1f242e |
| ამაღლებული ფონი/hover `ink-100` | #eef0f4 | იგივე | #283040 |
| გამყოფი `line`=ink-200 (დეკორატიული) | #dde1e9 | იგივე | #353d4d |
| კონტროლის საზღვარი `line-strong`=ink-300 | #c2c9d6 | #7b8599 | #747d93 |
| იკონები/გამყოფი ink-400 | #97a1b5 | #6f798e | #7f889d |
| მეორადი ტექსტი `fg-muted`=ink-500 | #657086 | #5f6a80 | #a3abbd |
| ტექსტი ink-600 / 700 / 800 | #56617a / #454e63 / #333a4a | იგივე | #b8bfcd / #cad0da / #dde1e8 |
| ძირითადი ტექსტი `fg`=ink-900 | #1e2330 | იგივე | #f0f2f6 |
| primary-50 / 100 (ტინტი) | #eef3ff / #dbe5ff | იგივე | #1f2749 / #252f62 |
| primary-500 (focus, საზღვარი) | #3a5bf5 | იგივე | #7f98ff |
| primary-600 `primary` (solid fill) | #2440e0 | იგივე | #4466f7 |
| primary-hover / press | #1e33bd / #1d2f99 | იგივე | #3558ea / #2d4ed8 |
| primary-700 (ტექსტი ზედაპირზე/ტინტზე) | #1e33bd | იგივე | #a7bbff |
| accent-600 `accent` (ფასი, ფასდაკლება) | #c74407 | იგივე | #c74407 |
| accent-700 / 800 | #9e360e / #7f2e0f | იგივე | #a8390a / #8f320c |
| accent-50 | #fff8ed | იგივე | #33220f |
| success 50 / 600 / 700 | #ecfdf5 / #059669 / #047857 | იგივე | #14302a / #34d399 / #6ee7b7 |
| danger-50 / 100 | #fef2f2 / #fee2e2 | იგივე | #331a1f / #421d23 |
| danger-500 (შეცდომის საზღვარი) / 600 / 700 | #ef4444 / #dc2626 / #b91c1c | იგივე | #f87171 / #dc2626 / #b91c1c |
| `danger-fg` (შეცდომის ტექსტი) | #dc2626 | #c81e1e | #fca5a5 |
| warning-50 / 500 / 600 (ტექსტი) | #fffbeb / #f59e0b / #aa5d05 | იგივე | #33290f / #f59e0b / #fbbf24 |
| `media` (ფოტოს ფილა, ყველა თემაში) | #eef0f4 (`media-shade` #dde1e9) | იგივე | იგივე |
| `scrim` (მოდალის ფონი, `/50`) | #12151d | იგივე | #05070a |

ხატვის წესი: ტექსტი/ფონი ყოველთვის როლით (`text-ink-900`, `bg-surface`), hex-ი კომპონენტში არ იწერება. `src/utils/palette.test.js` ამოწმებს storefront-ის წყვილებს AA-სთვის ორივე თემაში.

### კონტრასტი (WCAG ფორმულით გამოთვლილი, ხელით)
Admin (light): ink-900 / canvas **14.76:1**; ink-900 / white **15.69:1**; ink-600 / white **6.20**, / canvas **5.83**; ink-500 / white **4.98**, / canvas **4.69**, / ink-100 **4.37 (< 4.5)**; ink-700 / white 8.32, / ink-100 7.29.
Ღილაკები (admin = light): ტექსტი white on primary-600 **7.28**; on primary hover **9.28**; white on accent-600 **4.93**, accent-700 **7.03**; white on danger-600 **4.83**, danger-700 **6.47**; secondary (white on ink-900) **15.69**, hover ink-800 **11.38**; outline ink-800 / white **11.38**.
ბეჯები/ბანერები: danger-700 / danger-50 **5.92**; warning-600 / warning-50 **4.74**; success-700 / success-50 **5.21**; primary-700 / primary-50 **8.35**; accent-800 / accent-50 **8.65**; ink-700 / ink-100 **7.29**; danger-600 / danger-50 (admin `danger-fg`) **4.41 (< 4.5)**.
Storefront light: ink-500 `#5f6a80` / white **5.44**, / ink-50 **5.12**, / ink-100 **4.77**; `danger-fg` #c81e1e / danger-50 **5.24**; ink-900 / ink-50 = admin (14.76).
Storefront dark: ink-900 / canvas **15.39**, / surface **13.87**; ink-500 / surface **6.75**, / ink-100 **5.74**; white on primary-600 **4.68**, on hover **5.62**; `danger-fg` / danger-50 **8.45**; secondary ღილაკი (surface on ink-900) **13.87**.
არა-ტექსტური: focus ring primary-500 `#3a5bf5` / white ≈ 5.5 (>3:1; მხოლოდ შეფასება, ზუსტად არ გამომითვლია). Admin control-border ink-300 / white **1.66 (< 3:1)**; ink-400 icon / white **2.60** — იხ. nits.
ვერ დადგინდა: disabled მდგომარეობების კონტრასტი (WCAG-ით გათავისუფლებულია; `primary-300` + white ≈ 2.1).

## 3. ტიპოგრაფია
- ოჯახი (`font-sans`): `"Noto Sans Georgian", Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`. Noto Sans Georgian self-hosted (`/fonts/*.woff2`, `font-display: swap`), ქართული + ლათინური subset, წონები 400/500/600/700, `unicode-range` ორივე დამწერლობისთვის. ქართულის მხარდაჭერა: **კი** (Noto Sans Georgian; დასტური `fonts.css`-იდან: georgian subset-ის ფაილები და `unicode-range` U+10A0–10FF, მთავრული U+1C90–1CBF; WebSearch-ით არ გადამიმოწმებია). Inter არ იტვირთება (მხოლოდ სიაშია); fallback-ების (Roboto, Arial, Helvetica Neue) ქართული დაფარვა **ვერ დადგინდა**; system-ui/Segoe UI ჩვეულებრივ აფარებს. ლიცენზია: SIL OFL (Google Fonts; კოდში არ წერია).
- ზომები (Tailwind default + `2xs`): 2xs 11/16px · xs 12/16 · sm 14/20 · base 16/24 · lg 18/28 · xl 20/28 · 2xl 24/32 · 3xl 30/36 · 4xl 36/40 · 5xl 48/1.
- ველის ტექსტი (`.field-text`): 16px მობილურზე, 14px `sm:`-დან (iOS zoom-ის გამო; `maximum-scale` აკრძალულია).
- Storefront h1: `text-2xl sm:text-3xl font-bold tracking-tight text-ink-900`; Home hero: `text-3xl sm:text-4xl lg:text-5xl font-bold leading-tight tracking-tight`. ბარათის სათაური `text-sm font-semibold leading-tight`; ბრენდის ეტიკეტი `text-2xs font-semibold uppercase tracking-wide`.
- Admin h1: `text-lg font-semibold text-ink-900`; ქვესათაური `text-sm text-ink-600`; სექციის h2 `text-sm font-semibold`; ცხრილის th `text-xs font-medium uppercase tracking-wide text-ink-500`; რიცხვები `tabular-nums`.
- Weights: 400 ტექსტი, 500 ლეიბლი/ბეჯი, 600 ღილაკი/სათაური, 700 h1.

## 4. დაშორებები და layout
- Spacing: Tailwind-ის 4px შკალა (1=4px … 4=16px, 6=24px). ბარათის padding `p-4`/`p-3.5 sm:p-4`; admin სექცია `p-4`, გვერდი `p-4 md:p-6`; ბლოკებს შორის `space-y-4`, ფილტრებს `gap-2`.
- Breakpoints (Tailwind default, არ არის გადაწერილი): sm 640 · md 768 · lg 1024 · xl 1280 · 2xl 1536. მობილური ბაზა ≈390px.
- Storefront კონტეინერი `.container-page`: `max-w-container` **1400px**, `px-4 sm:px-6 lg:px-8`. პროდუქტის grid: 2 → `sm` 3 → `lg` 4 სვეტი, `gap-4`.
- Admin: sidebar `w-56` (`md:` და ზევით; ქვემოთ დამალულია — მობილური ნავიგაცია ადმინში **არ არის**), header `h-14`, `main` `min-w-0 flex-1`; ორსვეტა დეტალი `lg:grid-cols-[1fr_20rem]`; ცხრილი `min-w-[52rem]` საკუთარ `overflow-x-auto`-ში.
- z-index: header 40 · drawer 50 · modal 60 · toast 70 · skip-link 80.

## 5. ფორმები
- Radii: `rounded-control` 0.625rem (ღილაკი, input, ფილა) · `rounded-card` 0.875rem (ბარათი, toast, მოდალი) · `rounded-pill` (ბეჯი). Admin-ში დამატებით პირდაპირ Tailwind: `rounded-xl` (ცხრილი/სექცია), `rounded-lg` (nav, ბანერი, ძებნა).
- ჩრდილები: `shadow-sm` (solid ღილაკი); `card` `0 1px 2px / 0 1px 3px` (rgb 18 21 29 / .04–.06); `card-hover` `0 10px 24px -6px /.14`; `popover` `0 12px 32px -8px /.22` (toast, მოდალი); `header` `0 1px 0 0 /.06`; `glow` (hover ბარათი, primary-400/600) — dark-ზე ჩრდილის ნაცვლად. Admin ბარათებს ჩრდილი არ აქვს, მხოლოდ `border border-ink-200`.
- ანიმაცია: fade-in 180ms, slide-up 220ms, sheet-up/slide-in 260ms; `prefers-reduced-motion` ყველაფერს ასუსტებს ~0.

## 6. კომპონენტები და მდგომარეობები
**Focus (გლობალური):** `:focus-visible` → `ring-2 ring-primary-500 ring-offset-2 ring-offset-surface rounded-sm`. შიდა override-ები: Input/Select `focus:ring-2 ring-primary-500/30 + border-primary-500`; admin nav `outline-2 outline-offset-2 outline-accent-700`; admin header ბმულები `outline-ink-500`.

**Button** (`components/common/Button.jsx`; საერთოა storefront-ისა და admin-ის): `font-semibold`, `transition-colors 150ms`. ზომები: xs h-8 px-3 text-xs · sm h-9 px-3.5 text-sm · md (default) h-11 px-5 text-sm · lg h-12 px-6 text-base · icon 40×40. ვარიანტები:
- primary: `bg-primary-600 text-white`, hover `primary-hover`, active `primary-press`, disabled `primary-300`.
- secondary: **მუქი ინკი** `bg-ink-900 text-surface`, hover ink-800, disabled ink-400 (dark თემაში ინვერსია ავტომატურია).
- outline (ფაქტობრივად admin-ის "მეორადი": ConfirmDialog-ის "გაუქმება"): `border-ink-300 bg-surface text-ink-800`, hover `border-primary-400 bg-primary-50 text-primary-700`, disabled `text-ink-400`.
- danger: `bg-danger-600 text-white`, hover/active `danger-700`, disabled `danger-500/50`.
- accent (admin-ში "პირველადი" ქმედება: ახალი პროდუქტი, სტატუსის შეცვლა): `bg-accent-600 text-white`, hover 700, active 800, disabled accent-200.
- ghost (იკონ-ღილაკები ცხრილში), link.
- loading: `loading` prop → `Loader2 h-4 w-4 animate-spin`, `disabled` + `aria-busy`. disabled: `cursor-not-allowed`.

**Input / Select / Textarea:** h-11, `rounded-control border border-ink-300 bg-surface px-3.5 text-ink-900`, placeholder ink-500; focus იხ. ზემოთ; error: `border-danger-500` + `ring-danger-500/30`, ქვემოთ `AlertCircle` + `text-xs font-medium text-danger-fg`, `aria-invalid`/`aria-describedby`; hint `text-xs text-ink-500`; disabled `bg-ink-100 text-ink-500`; ლეიბლი `text-sm font-medium text-ink-800`, required `*` danger-fg. Admin სიების ძებნა — ნედლი `<input>` h-9 `rounded-lg`, focus `accent-600` (იხ. nits). Checkbox (admin): `h-4 w-4 rounded border-ink-300 text-accent-600 focus:ring-accent-600/30`.

**Badge** (storefront `common/Badge.jsx`, pill, `font-semibold`, md `px-2 py-0.5 text-xs`, sm text-2xs): new = primary-600/white · discount = accent-600/white · danger = ink-900/surface · success/warning = 50-ფონი + ring · neutral `ink-100/ink-700` · outline. **Admin statusები** (`StatusBadge.jsx`, `statuses.jsx`): `rounded-full px-2 py-0.5 text-xs font-medium`; შეკვეთა: მიღებული ink-100/700 · დადასტურებული primary-50/700 · მუშავდება warning-50/600 · გაგზავნილი accent-50/800 · მიწოდებული success-50/700 · გაუქმებული danger-50/700.

**ბარათი:** storefront `rounded-card border border-line bg-surface`, hover `-translate-y-0.5 border-primary-400/60 shadow-glow`; admin სექცია `rounded-xl border border-ink-200 bg-white p-4`.

**ცხრილი (admin `DataTable`):** კონტეინერი `rounded-xl border border-ink-200 bg-white`; th იხ. §3, `px-3 py-2.5`; სტრიქონი `border-b border-ink-100 hover:bg-ink-50`; loading = 6 `Skeleton h-10`; empty = გადმოცემული `EmptyState`; `caption` sr-only. Pagination: `h-9 rounded-lg border-ink-300`, disabled `opacity-40`.

**დიალოგი:** `Modal` — `role="dialog" aria-modal`, ESC, focus trap, ფოკუსის დაბრუნება; ფონი `bg-scrim/50`; პანელი `bg-surface shadow-popover rounded-card`, სათაური `border-b px-5 py-4 text-base font-semibold`, ზომები sm…2xl (default lg). `ConfirmDialog` (admin): ტექსტი `p-5 text-sm text-ink-600`, ღილაკები მარჯვნივ `gap-2`: outline sm "გაუქმება" + `variant` (default danger) sm; confirm `loading` ხანგრძლივობისას, დახურვა დაბლოკილია.

**Toast** (storefront, `Toast.jsx`): ქვემოთ, `max-w-sm rounded-card border bg-surface shadow-popover px-4 py-3`, საზღვარი `success/danger/primary-500/30`, იკონი 20px (`CheckCircle2` success-600 · `AlertCircle` danger-fg · `Info` primary-700), ტექსტი `text-sm font-medium`, ქმედება `text-primary-700 font-semibold`, ჯგუფი `aria-live="polite"`. Admin-ში toast-ის გამოყენება **ვერ დადგინდა** (admin-ი inline ბანერებს იყენებს).

**ბანერები (admin, inline):** შეცდომა — `<p role="alert" class="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">` (OrderDetail, ProductForm); გაფრთხილება — `rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-600` + `AlertTriangle h-4 w-4` (ProductForm:351), საზღვრის გარეშე.

**ნავიგაცია:** storefront `Header` — `sticky top-0 z-header border-b border-line bg-canvas/85 backdrop-blur`, მობილურზე `MobileMenu` drawer (`Modal position=left`). Admin sidebar (`md:`+): `w-56 bg-white border-r`, ელემენტი `rounded-lg px-3 py-2 text-sm`, აქტიური `bg-accent-50 text-accent-800 font-medium`, hover `bg-ink-100`; top bar h-14, "მაღაზიაში" (ბორდერიანი ბმული) და "ანგარიშიდან გასვლა" (hover danger-50/700).

## 7. გვერდის მდგომარეობები
- **Loading:** `Skeleton` (`bg-ink-200/70`, shimmer 1.6s) — spinner-ის ნაცვლად; ბარათის სკელეტონი ბარათის იდენტური გეომეტრიით; admin დეტალი `Skeleton h-96 w-full`; სათაურში "იტვირთება…".
- **Empty:** `EmptyState` — `rounded-card border border-dashed border-ink-300 bg-surface px-6 py-14 text-center`, 64px წრე `bg-ink-100` + 28px `text-ink-500` იკონი, სათაური `text-lg font-semibold`, აღწერა `text-sm text-ink-600`, მოქმედების `Button` (თუ არსებობს).
- **Error:** `ErrorState` — `role="alert"`, `rounded-card border-danger-100 bg-danger-50 py-12 text-center`, `AlertTriangle` danger-fg 56px წრეში `bg-danger-100`, სათაური ink-900, ტექსტი ink-700, `outline` "ხელახლა" ღილაკი `RotateCcw`-ით.

## 8. სურათები და იკონები
- იკონები: **lucide-react** (MIT), 16px (`h-4 w-4`) ღილაკებსა და ველებში, 20px toast/ნავიგაცია, `aria-hidden="true"`; იკონ-ღილაკს `aria-label` აქვს. სხვა ნაკრები არ არის.
- პროდუქტის ფოტო `ProductImage` — `aspect-square rounded-control` ღია ფილაზე (`media` #eef0f4, ყველა თემაში), ბარათის კიდიდან `p-2`-ით; hover `scale-1.04`. ფოტოს არქონისას placeholder-ის ზუსტი წესი `ProductImage.jsx`-ში (ამ დოკუმენტისთვის არ გადამიმოწმებია — ვერ დადგინდა).
- ლოგო: `components/layout/Logo.jsx` (ამ დოკუმენტისთვის არ შემომიმოწმებია). Admin-ში `Store` იკონი accent-600-ით + "VoltBox" + ბეჯი "ადმინი" (`bg-ink-100 text-ink-600 text-[11px]`).

## 9. Admin: destructive actions and trash (Stage 2 — შეკვეთების სანაგვე)
მხოლოდ არსებული ტოკენები და კომპონენტები; ახალი ფერი/კომპონენტი არ შემოდის. ტექსტი ქართულია, პირდაპირ JSX-ში (admin-ის წესი). ყველა admin ფერი light-ია.
1. **"წაშლა" (OrderDetail):** `Button variant="danger" size="sm"` + `Trash2 h-4 w-4` (როგორც ProductList-ში), იმავე ღილაკების რიგში, სადაც `allowedTransitions` (`mb-4 flex flex-wrap gap-2`), სტატუსის ღილაკების მარჯვნივ/ბოლოს. დადასტურება: `ConfirmDialog` როგორც `ProductList` (`title` + `description` რა მოხდება და როდის წაიშლება სამუდამოდ, `confirmLabel="წაშლა"` — ღილაკის სიტყვა = დიალოგის ღილაკის სიტყვა, `variant="danger"`). შეცდომა — OrderDetail-ის `actionError` ბანერი (`role="alert"`, danger-50/700, 5.92:1).
2. **გაფრთხილების ბანერი სანაგვეში მყოფ შეკვეთაზე:** ProductForm:351-ის გაფრთხილების ბანერის პატერნი — `rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-600` (4.74:1) + `AlertTriangle h-4 w-4`; ტექსტი: წაშლის თარიღი `dateOnly()`-ით (`admin/format.js`, როგორც ProductList-ის "დამატებული" სვეტი). ადგილი: `<header>`-სა და სტატუსის ღილაკებს შორის. რადგან ტექსტი შეიცავს სტატუსს/თარიღს და არა სიახლეს, `role` არ სჭირდება (ProductForm-ის გაფრთხილებასაც არ აქვს). ამავე ბანერში "აღდგენა" `outline sm` ღილაკი (აღდგენის ქმედება გვერდზეც უნდა იყოს).
3. **"სანაგვე" გადამრთველი სიაზე (OrderList):** ProductList-ის `lowStock` checkbox-ის პატერნი ზუსტად: `<label class="mb-3 flex w-fit items-center gap-2 text-sm text-ink-700">` + checkbox `h-4 w-4 rounded border-ink-300 text-accent-600 focus:ring-accent-600/30`; მდგომარეობა URL-ის query-ში `setParam('trash', event.target.checked)`. ფილტრების პანელის ქვემოთ, ცხრილის ზემოთ. ჩართულზე `EmptyState`: "სანაგვე ცარიელია" (იგივე `EmptyState`, ღილაკის გარეშე).
4. **სტრიქონის ღილაკები (სანაგვის რეჟიმში):** ახალი "ქმედებების" სვეტი — `align: 'right'`, `render: <span className="flex justify-end gap-1">` (ProductList-ის `actions` სვეტი). "აღდგენა" — `Button variant="outline" size="xs"` (admin-ის მეორადი = ConfirmDialog-ის "გაუქმება"; `variant="secondary"` არ გამოიყენო — ის მუქი ინკის solid ღილაკია). "სამუდამოდ წაშლა" — `Button variant="danger" size="xs"`, ხსნის `ConfirmDialog`-ს `confirmLabel="სამუდამოდ წაშლა"` (ProductList-ის ზუსტი სიტყვა), `variant="danger"`, აღწერაში "ქმედება შეუქცევადია". `aria-label` რიგის ნომრით (`${order.orderNumber} — აღდგენა`), როგორც ProductList-ში. in-flight: `loading` prop. რიგის სტატუსი — `OrderStatusBadge`; სანაგვის მარკერისთვის (თუ საჭიროა) neutral pill `bg-ink-100 text-ink-700` (7.29:1) — **(დამატებულია)**, ახალი ფერის გარეშე.
5. კონტრასტი: white on danger-600 4.83:1, on danger-700 (hover) 6.47:1; outline ink-800/white 11.38:1 — AA სრულდება. წაშლისას აკრძალული: ახალი hex, `dark:`, `window.confirm`.
ვერ დადგინდა: წარმატების შეტყობინება აღდგენის/წაშლის შემდეგ (admin-ში toast-ის გამოყენება არ ჩანს) — უმარტივესი: სტრიქონი უბრალოდ ქრება და სია ახლდება (`reloadToken`, როგორც ProductList-ში).
