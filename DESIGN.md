# VoltBox — DESIGN.md

წყარო: Storefront — `design-reference/Site.dc.html` (inline `style`, `<helmet><style>`, `renderVals()` → `light`, `darkT`) + არსებული `frontend/tailwind.config.js`, `src/index.css`, `src/fonts.css`, `src/components/**`. Admin — დაყენებული, უცვლელი (ბოლო სექცია "Admin panel (frozen)"). მარკერები: `(დამატებულია)` = მოკაპ-ში არ არის, ჩემი მინიმალური შევსება; `(AA)` = მოკაპის მნიშვნელობა WCAG AA-ს არ აკმაყოფილებდა და შეცვლილია; `(ვერ დადგინდა)` = ვერ დავადგინე.
ტექსტი, ფასი, ტელეფონი, მიწოდების ზღვარი მოკაპიდან არ გადმოდის — ყველაფერი რჩება არსებული i18n-იდან / `constants/index.js`-იდან / `GET /delivery`-დან.

## 1. მიმართულება
თბილი "ქაღალდისფერი" რედაქციული სტილი: კრემისფერი (light) ან თითქმის შავი (dark) ფონი, თხელი 1px ხაზები, ნახევრად კვადრატული კუთხეები (2px), სერიფული სათაურები, ერთადერთი ოქროსფერი აქცენტი და მუქი (dark თემაში ოქროსფერი) მყარი ღილაკები. მიზეზი: ელექტრონიკის მაღაზია, რომელიც მოკაპში პრემიუმ-სიმშვიდეს ირჩევს, არა "ტექნო" ფერებს. ვერიდებით: ლურჯ primary-ს, ჩრდილებს ბარათზე, დიდ რადიუსებს, გრადიენტულ ტექსტს, `dark:` კლასებს (თემა = პალიტრის ცვლადები), ფერს როგორც ერთადერთ სიგნალს (სტატუსი = ტექსტი + ფერი).

## 2. ფერები (storefront: light და dark)
Tailwind-ში ფერი როლით იწოდება (`--c-<name>-<step>`). სამი პალიტრა ერთი ფორმით: `admin` (უცვლელი), `light`, `dark`. ნაბიჯის სამუშაო ყველა თემაში ერთია (იხ. `tailwind.config.js` header); მხოლოდ მნიშვნელობა მოძრაობს. ახალი როლი ოთხია: `on-primary`, `footer`, `glow`, `outline` — თითოეულს admin-ის მნიშვნელობაც აქვს, რომ ფორმა არ გაიყოს.

### 2.1 მოკაპის ყოველი ტოკენი → როლი
| მოკაპი | light | dark | როლი / შენიშვნა |
|---|---|---|---|
| `bg` | #F7F4EE | #0E0E0F | ink-50 `canvas` (გვერდის ფონი) |
| `surface` | #FFFFFF | #131315 | `surface` (ბარათი, header, input, მოდალი) |
| `line` | #E6E0D4 | #26262A | ink-200 `line` (დეკორატიული 1px ხაზი) |
| `line2` | #D6CDBC | #3A3A40 | **ორი გამოყენება, ორი როლი.** (a) მოკაპში `line2` არის კატეგორიების ღილაკის, თემის გადამრთველის, carousel prev/next-ის, hero-ს outline CTA-ს კონტური და ერთი დეკორატიული ზოლი — ყველა ეს კონტროლი თავის ლეიბლს/იკონს თვითონ ატარებს, ამიტომ WCAG 1.4.11 კონტურისთვის 3:1-ს არ მოითხოვს → **ახალი `outline`** = `line2` უცვლელი (#D6CDBC / #3A3A40), რომ outline ღილაკები მოკაპივით რბილი დარჩეს. (b) ძებნის ქვედა ხაზი (ველის ერთადერთი საზღვარი) და ტექსტური ველი → ink-300 `line-strong` **(AA)**: light → **#8C8474**, dark → **#6A6A70**; იგივე მნიშვნელობა ink-400-ს (იკონები, გამყოფები) |
| `text` | #1C1B19 | #EDE9E3 | ink-900 `fg` |
| `muted` | #6F6A62 | #A19B91 | ink-500 `fg-muted` **(AA)**: light → **#6D6860** (footBg-ზე იყო 4.48) |
| `gold` | #A8854A | #C9A96E | primary-500 (ორნამენტი, იკონი, ღია საზღვარი, focus ring) **(AA)**: light → **#A18046** (footBg-ზე იყო 2.86) |
| `goldTxt` | #8C6A34 | #C9A96E | primary-700 (ტექსტი: ეტიკეტი, ბმული, ფუტერის სათაური) **(AA)**: light → **#826330** (footBg-ზე იყო 4.14) |
| `btnBg` | #1C1B19 | #C9A96E | primary-600 (მყარი ღილაკი, checked box, ჩარჩო-სლაიდერი) |
| `btnTxt` | #F7F4EE | #0E0E0F | **ახალი** `on-primary` (ტექსტი/იკონი primary-ზე) |
| `footBg` | #EFEAE0 | #0A0A0B | **ახალი** `footer` (light-ში იგივე hex, რაც ink-100) |
| `glow` | gradient #FBF6EC → #F6F0E4 → 0 | #2B2720 → #1A1917 → 0 | **ახალი** `glow` = ცენტრის ფერი (#FBF6EC / #2B2720); მეორე გაჩერება = primary-50 (#F6F0E4 / #1A1917 — ზუსტად მოკაპის შუა ფერი) |
| `device`, `deviceLine`, `deviceShadow`, `pedestal` | — | — | **არ გამოიყენება**: ტელეფონის/Power Bank-ის ნახატი ერთ კატეგორიაზე მიანიშნებს და სიტყვებს (N° 01 — POWER BANK) შეიცავს; hero-ს ორნამენტი = ბრენდის ნიშანი (იხ. §7) |
| `placeholder` | #C8BEAC | #5A554C | ink-400 (ფილა ორივე თემაში ღიაა, ამიტომ მუქი dark-მნიშვნელობა არ ვარგა) |
| `imgBg` | radial #FFF → #F5F1E9 → #EDE7DB | radial #26231E → #171618 → #111113 | `media` = ბრტყელი **#F5F1E9** (ორივე თემაში), `media-shade` = **#EDE7DB**; gradient არ გამოიყენება (მარტივად; ფოტო `mix-blend-multiply`-ით ფილას ერწყმის), dark-მნიშვნელობა არ გამოიყენება (Decision Log 2026-10-19) |
| `a:hover{color:#A8854A}` | | | **(AA)** gold ტექსტად 3.13:1 — ჩანაცვლებულია: ბმულის hover = primary-700 |

### 2.2 სრული პალიტრა (T27 ამას გადაიტანს `tailwind.config.js`-ში)
`admin` სვეტი = ფაილში დღევანდელი, არ იცვლება. `=` = იგივე, რაც admin.

| როლი | admin | light | dark |
|---|---|---|---|
| ink-50 `canvas` | #f7f8fa | #F7F4EE | #0E0E0F |
| ink-100 (ამაღლებული ფონი, hover) | #eef0f4 | #EFEAE0 | #1D1D20 |
| ink-200 `line` | #dde1e9 | #E6E0D4 | #26262A |
| ink-300 `line-strong` | #c2c9d6 | #8C8474 | #6A6A70 |
| ink-400 | #97a1b5 | #8C8474 | #6A6A70 |
| ink-500 `fg-muted` | #657086 | #6D6860 | #A19B91 |
| ink-600 | #56617a | #58534C | #B8B2A8 |
| ink-700 | #454e63 | #46423C | #CDC8BF |
| ink-800 | #333a4a | #302D29 | #DFDAD2 |
| ink-900 `fg` | #1e2330 | #1C1B19 | #EDE9E3 |
| ink-950 | #12151d | #0E0E0F | #F7F4EE |
| `surface` | #ffffff | #FFFFFF | #131315 |
| `media` | #eef0f4 | #F5F1E9 | #F5F1E9 |
| `media-shade` | #dde1e9 | #EDE7DB | #EDE7DB |
| `scrim` (`/50` ფონი) | #12151d | #1C1B19 | #000000 |
| primary-50 (ტინტი) | #eef3ff | #F6F0E4 | #1A1917 |
| primary-100 (ტინტი, active) | #dbe5ff | #F1E9D8 | #2B2720 |
| primary-200 (ტინტის საზღვარი, selection) | #bfd0ff | #DCCBA6 | #3A3326 |
| primary-300 (disabled მყარი ფონი) | #94b0ff | #C9C2B3 | #5C5240 |
| primary-400 (hover საზღვარი) | #6285ff | #BDA06C | #D8BD84 |
| primary-500 (ორნამენტი, focus) | #3a5bf5 | #A18046 | #C9A96E |
| primary-600 `primary` (მყარი ფონი) | #2440e0 | #1C1B19 | #C9A96E |
| primary-700 (ტექსტი) | #1e33bd | #826330 | #C9A96E |
| primary-800 (ტექსტი ტინტზე) | #1d2f99 | #6B5226 | #D8BD84 |
| primary-900 / 950 | #1e2e79 / #141c47 | #4F3B17 / #2E2310 | #E8D6B0 / #F3EBD8 |
| primary-hover / primary-press | #1e33bd / #1d2f99 | #3A3733 / #0E0E0F | #D8BD84 / #B49456 |
| accent 50 / 100 / 200 / 300 | #fff8ed / #ffefd4 / #ffdba8 / #ffc071 | = | #33220f / #422a10 / #5c3a17 / #8a4a17 |
| accent-400 (ვარსკვლავები) | #ff9c38 | #d26a08 | #ffa24a |
| accent 500 / 600 / 700 / 800 / 900 | #ff7f11 / #c74407 / #9e360e / #7f2e0f / #66250c | = | #ff8a2a / #c74407 / #a8390a / #8f320c / #66250c |
| accent-fg (ფასდაკლების ტექსტი) | #c74407 | #C24307 **(AA, ახალ canvas-ზე 4.49 იყო)** | #ffa24a |
| success 50 / 100 / 500 / 600 / 700 | #ecfdf5 / #d1fae5 / #10b981 / #059669 / #047857 | = | #14302a / #173a31 / #34d399 / #34d399 / #6ee7b7 |
| danger 50 / 100 / 500 / 600 / 700 | #fef2f2 / #fee2e2 / #ef4444 / #dc2626 / #b91c1c | = | #331a1f / #421d23 / #f87171 / #dc2626 / #b91c1c |
| danger-fg | #dc2626 | #c81e1e | #fca5a5 |
| warning 50 / 100 / 500 / 600 | #fffbeb / #fef3c7 / #f59e0b / #aa5d05 | = | #33290f / #423411 / #f59e0b / #fbbf24 |
| **`on-primary`** (ახალი) | #ffffff | #F7F4EE | #0E0E0F |
| **`footer`** (ახალი) | #ffffff | #EFEAE0 | #0A0A0B |
| **`glow`** (ახალი) | #eef3ff | #FBF6EC | #2B2720 |
| **`outline`** (ახალი; კონტროლის კონტური, რომელსაც ლეიბლი/იკონი ატარებს) | #c2c9d6 | #D6CDBC | #3A3A40 |

ახალი როლების admin მნიშვნელობა = რასაც admin დღეს ხატავს: `on-primary` = ტექსტი primary-600-ზე (`text-white`); `footer` = ფუტერის ფონი (`bg-surface`); `outline` = admin-ის outline ღილაკის საზღვარი დღეს (`Button.jsx`: `border-ink-300` = #c2c9d6; secondary მყარი ღილაკია, საზღვრის გარეშე); `glow` — admin არ ხატავს, მნიშვნელობა primary-50 (არავის ეხება). `theme-color` meta: light = #F7F4EE, dark = #0E0E0F.

### 2.3 როლები, რომლებსაც storefront ხატავს, მოკაპს კი არა აქვს
| რა | როლი-ნაბიჯი (light / dark) |
|---|---|
| danger: ტექსტი / ტინტი / საზღვარი / ფონი | danger-fg / danger-50 / danger-500 / danger-600 (hover, active danger-700) |
| success: ტექსტი / ტინტი / საზღვარი / იკონი | success-700 / success-50 / success-500 (`/30`) / success-600 |
| warning: ტექსტი / ტინტი / საზღვარი | warning-600 / warning-50 / warning-500 (`/30`) |
| ფასდაკლება და ძველი ფასი | ბეჯის ფონი accent-600 + `text-white`; დაზოგვის ტექსტი accent-fg; ძველი ფასი ink-500 + `line-through` (accent-ს ფასი არ ეკუთვნის) |
| focus ring | primary-500: `ring-2 ring-primary-500 ring-offset-2 ring-offset-surface` (ღილაკის რადიუსს მიჰყვება) |
| disabled | მყარი ფონი → primary-300 (ტექსტი on-primary); outline/ghost → ტექსტი ink-400, საზღვარი ink-200; input → ფონი ink-100, ტექსტი ink-500; (WCAG ათავისუფლებს) |
| outline-ღილაკის / წრიული იკონ-ღილაკის / კატეგორიების ღილაკის / hero outline CTA-ს კონტური | `outline` (დეკორატიული ზოლიც); hover → primary-500 |
| input (ტექსტური ველის საზღვარი — ერთადერთი ინდიკატორი, 3:1) : საზღვარი / ფონი / placeholder | ink-300 / surface / ink-500; hover საზღვარი primary-500; focus საზღვარი primary-500 + `ring-2 ring-primary-500/30`; error საზღვარი danger-500 + `ring-danger-500/30` |
| ღილაკის hover / pressed | primary: `primary-hover` / `primary-press`; secondary: ink-800 / ink-950; outline: საზღვარი primary-500 + ფონი primary-50 + ტექსტი primary-700 / ფონი primary-100; ghost: ფონი ink-100 / ink-200; danger: danger-700 / danger-700; accent: 700 / 800 |
| scrim | `scrim` + `/50` |
| skeleton | ფონი ink-200 + `/70`, shimmer `via-surface/60` (უცვლელი) |
| selection | `::selection` ფონი primary-200, ტექსტი ink-900 |

### 2.4 კონტრასტი (WCAG ფორმულა, ორი ათწილადი)
**მოკაპის მნიშვნელობები, რომლებიც ვერ გადიოდა (ძველი → ახალი, თანაფარდობა):**
- light `line2` როგორც **ველის საზღვარი** (≥ 3): #D6CDBC → **#8C8474** (ink-300); #FFFFFF-ზე 1.58 → 3.71, canvas-ზე 1.44 → 3.38, ink-100-ზე 1.32 → 3.09. (გეგმის შეფასება ≈1.6 დადასტურდა.)
- dark `line2` როგორც ველის საზღვარი: #3A3A40 → **#6A6A70**; surface-ზე 1.64 → 3.45, canvas-ზე 1.71 → 3.59, ink-100-ზე 1.49 → 3.13. (გეგმა ≈1.6 დადასტურდა.)
- **`outline` (გადაწყვეტილება)**: `line2` ღილაკების კონტურად უცვლელი რჩება (#D6CDBC / #3A3A40) და **არ შედის `PAIRS`-ში**. მიზეზი: WCAG 1.4.11 3:1-ს მოითხოვს მხოლოდ საზღვარზე, რომელიც კონტროლის ერთადერთი ინდიკატორია (ტექსტური ველი); ღილაკი/წრიული იკონ-ღილაკი თავის ლეიბლს ან იკონს (აქვს `aria-label`) თვითონ ატარებს და მისი კონტური მხოლოდ დეკორია; მუქი #8C8474 ყველა outline ღილაკს მოკაპზე გაცილებით მკაცრს გახდიდა, მფლობელს კი მოკაპის გამეორება უნდა. ინფორმაციისთვის (არ არის ტესტში): light #D6CDBC — surface 1.58, canvas 1.44; dark #3A3A40 — surface 1.64, canvas 1.71. ამიტომ `palette.test.js`-ს მხოლოდ "defines the same tokens in every theme" ფორმის ტესტი ეხება `outline`-ს (admin/light/dark სამივეში არსებობს); კონტრასტის ტესტი — არა. ტექსტი/იკონი ამ ღილაკებზე იზომება ჩვეულებრივ (ink-900/primary-500 წყვილები).
- light `goldTxt` (ტექსტი ≥ 4.5): #8C6A34 → **#826330**; footBg/ink-100-ზე 4.14 → 4.64 (გეგმა ≈4.1 დადასტურდა), primary-50-ზე 4.38 → 4.90; canvas-ზე 4.53 → 5.07.
- light `muted`: #6F6A62 → **#6D6860**; footBg/ink-100-ზე 4.48 (გეგმა ≈4.5 — რეალურად 4.48, ვერ გადის) → 4.61; canvas-ზე 4.89 → 5.04.
- light `gold` როგორც ორნამენტი/იკონი/საზღვარი/focus (≥ 3): #A8854A → **#A18046**; footBg-ზე 2.86 → 3.08, canvas-ზე 3.13 → 3.36, surface-ზე 3.43 → 3.69. როგორც ტექსტი gold 3.13 (გეგმა ≈3.1 დადასტურდა) — ამიტომ gold ტექსტად არსად გამოიყენება, `a:hover` → primary-700 (5.07 canvas-ზე).
- არა-მოკაპი: light `accent-fg` #c74407 → **#C24307** (ახალ canvas-ზე 4.49 → 4.67).
- გადის ცვლილების გარეშე: `btnTxt`/`btnBg` light 15.68 (გეგმა ≈15.7 ✓), dark 8.62 (≈8.6 ✓); dark `muted`, `gold`, `text` ყველა ფონზე ≥ 6.99.

**`palette.test.js`-ის `PAIRS` (ფორმა უცვლელი; T27 ძველ სიას ამით ცვლის). `colour()`-ს უნდა ესმოდეს `on-primary`, `footer`, `media`, `primary-hover`, `primary-press` (სტრიქონი-როლები და ნაბიჯები უკვე იხსნება):**
```js
const PAIRS = [
  ['body text', 4.5, ['ink-900', 'ink-800', 'ink-700', 'ink-600'], ['canvas', 'surface', 'ink-100']],
  ['text on a hovered menu row', 4.5, ['ink-700'], ['ink-200']],
  ['muted text, placeholders, old price', 4.5, ['ink-500'], ['canvas', 'surface', 'ink-100', 'primary-50', 'footer']],
  ['links, eyebrow, brand label, active nav', 4.5, ['primary-700'], ['canvas', 'surface', 'ink-100', 'primary-50', 'primary-100', 'footer']],
  ['text on a tint', 4.5, ['primary-800'], ['primary-50']],
  ['text on a primary fill', 4.5, ['on-primary'], ['primary-600', 'primary-hover', 'primary-press']],
  ['white on solid fills', 4.5, ['white'], ['accent-600', 'accent-700', 'danger-600', 'danger-700']],
  ['secondary button, stock badge', 4.5, ['surface'], ['ink-900', 'ink-800', 'ink-950']],
  ['out-of-stock pill', 4.5, ['white'], ['scrim']],
  ['error text', 4.5, ['danger-fg'], ['canvas', 'surface', 'danger-50']],
  ['savings, discount text', 4.5, ['accent-fg'], ['canvas', 'surface', 'accent-50']],
  ['success text', 4.5, ['success-700'], ['surface', 'success-50']],
  ['warning text', 4.5, ['warning-600'], ['surface', 'warning-50']],
  ['selected text', 4.5, ['ink-900'], ['primary-200']],
  ['footer text', 4.5, ['ink-600'], ['footer']],
  ['control borders', 3, ['ink-300'], ['canvas', 'surface', 'ink-100', 'primary-50']],
  ['icons, separators', 3, ['ink-400'], ['canvas', 'surface', 'ink-100', 'primary-50']],
  ['error border', 3, ['danger-500'], ['canvas', 'surface', 'ink-100']],
  ['gold ornament, focus ring, round-button outline', 3, ['primary-500'], ['canvas', 'surface', 'ink-100', 'primary-50', 'footer']],
  ['checked box, active page, slider fill', 3, ['primary-600'], ['canvas', 'surface']],
  ['rating stars', 3, ['accent-400'], ['canvas', 'surface']],
  ['success icon', 3, ['success-600'], ['canvas', 'surface']],
  ['placeholder drawing on the photo tile', 3, ['ink-400'], ['media']],
];
```
**გამოთვლილი თანაფარდობები** (თანმიმდევრობა = ზემოთ fg × bg; `fg: l₁ l₂ … / d₁ d₂ …`, l = light, d = dark):
| რიგი | მინ. | light | dark |
|---|---|---|---|
| body — ink-900 | 4.5 | 15.68 · 17.21 · 14.35 | 15.96 · 15.35 · 13.91 |
| body — ink-800 | 4.5 | 12.48 · 13.70 · 11.43 | 13.87 · 13.34 · 12.09 |
| body — ink-700 | 4.5 | 9.09 · 9.98 · 8.32 | 11.59 · 11.14 · 10.10 |
| body — ink-600 | 4.5 | 6.94 · 7.62 · 6.35 | 9.16 · 8.81 · 7.98 |
| hovered row — ink-700 / ink-200 | 4.5 | 7.59 | 9.05 |
| muted — ink-500 (canvas, surface, ink-100, primary-50, footer) | 4.5 | 5.04 · 5.53 · 4.61 · 4.87 · 4.61 | 6.99 · 6.73 · 6.10 · 6.37 · 7.17 |
| links — primary-700 (canvas, surface, ink-100, primary-50, primary-100, footer) | 4.5 | 5.07 · 5.56 · 4.64 · 4.90 · 4.60 · 4.64 | 8.62 · 8.29 · 7.51 · 7.85 · 6.64 · 8.84 |
| tint — primary-800 / primary-50 | 4.5 | 6.47 | 9.65 |
| on-primary / (primary-600, hover, press) | 4.5 | 15.68 · 10.78 · 17.58 | 8.62 · 10.60 · 6.72 |
| white / (accent-600, accent-700, danger-600, danger-700) | 4.5 | 4.93 · 7.03 · 4.83 · 6.47 | 4.93 · 6.45 · 4.83 · 6.47 |
| surface / (ink-900, ink-800, ink-950) | 4.5 | 17.21 · 13.70 · 19.29 | 15.35 · 13.34 · 16.90 |
| white / scrim | 4.5 | 17.21 | 21.00 |
| danger-fg (canvas, surface, danger-50) | 4.5 | 5.23 · 5.74 · 5.24 | 10.17 · 9.78 · 8.46 |
| accent-fg (canvas, surface, accent-50) | 4.5 | 4.67 · 5.12 · 4.85 | 9.66 · 9.30 · 7.64 |
| success-700 (surface, success-50) | 4.5 | 5.48 · 5.21 | 12.17 · 9.27 |
| warning-600 (surface, warning-50) | 4.5 | 4.91 · 4.73 | 11.12 · 8.59 |
| ink-900 / primary-200 | 4.5 | 10.77 | 10.33 |
| ink-600 / footer | 4.5 | 6.35 | 9.40 |
| ink-300 და ink-400 (canvas, surface, ink-100, primary-50) | 3 | 3.38 · 3.71 · 3.09 · 3.26 | 3.59 · 3.45 · 3.13 · 3.27 |
| danger-500 (canvas, surface, ink-100) | 3 | 3.43 · 3.76 · 3.14 | 6.98 · 6.71 · 6.08 |
| primary-500 (canvas, surface, ink-100, primary-50, footer) | 3 | 3.36 · 3.69 · 3.08 · 3.25 · 3.08 | 8.62 · 8.29 · 7.51 · 7.85 · 8.84 |
| primary-600 (canvas, surface) | 3 | 15.68 · 17.21 | 8.62 · 8.29 |
| accent-400 (canvas, surface) | 3 | 3.30 · 3.62 | 9.66 · 9.30 |
| success-600 (canvas, surface) | 3 | 3.43 · 3.77 | 10.04 · 9.65 |
| ink-400 / media | 3 | 3.29 | 4.77 |

შენიშვნები: out-of-stock pill არის `scrim/85` ფილაზე — შეფასებულია მყარ scrim-ზე; რეალური ფონი `scrim/85` ღია ფილაზე ოდნავ ღიაა და თანაფარდობა ≈ 10.9 (light) / ≈ 15.5 (dark) რჩება — ორივე > 4.5. Disabled მდგომარეობა WCAG-ით გათავისუფლებულია, არ იზომება. Favicon-ის ბოლტი/ოქრო: #1C1B19 / #C9A96E = 7.69. ყველა ზემოთა წყვილი ≥ თავის მინიმუმს.

## 3. ტიპოგრაფია
**ოჯახები** (ყველა self-hosted `/fonts/*.woff2`, `font-display: swap`, Google CDN-ის გარეშე; ლიცენზია SIL OFL 1.1, წყარო Google Fonts css2 API):
- `font-sans` (უცვლელი, admin-იც ამას იყენებს): `"Noto Sans Georgian", Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` — ტექსტი, ღილაკი, ველი, ცხრილი. ქართული: კი (georgian subset); ლათინური: კი (latin subset).
- `font-serif` (ახალი): `"Noto Serif Georgian", Georgia, "Times New Roman", serif` — h1–h3, ბარათის სახელი, benefit/ფუტერის სათაური, კატეგორიის სახელი. ქართული: **კი** (georgian subset; WebSearch: Noto Serif Georgian ცვლადი, წონა 100–900, subset-ები georgian/latin/latin-ext, OFL — fontsource.org); ლათინური (`/en`): Noto Serif Georgian-ის latin subset.
- `font-display` (ახალი): `"Cormorant Garamond", "Noto Serif Georgian", Georgia, "Times New Roman", serif` — wordmark, hero display, ფასი, ბრენდის ეტიკეტი. ლათინური → Cormorant; **ქართული → Cormorant-ს ქართული გლიფები არ აქვს** (WebSearch-მა ქართული არც ერთ subset-ში არ აჩვენა: latin, latin-ext, cyrillic, vietnamese), ამიტომ ყველგან, სადაც Cormorant დგას, ქართული ტექსტი ავტომატურად Noto Serif Georgian-ზე გადადის (hero h1, კატეგორიის სახელი "Power Bank-ები", ფასი სიმბოლოსთან ერთად).
- `₾` (U+20BE): არც Noto Sans Georgian-ში (მხოლოდ Georgian ბლოკები — fontsource/Google-ის აღწერა; ჩატვირთულ georgian/latin subset-ებში U+20BE-ს range არ ფარავს), არც Noto Serif Georgian-ში არ არის; Cormorant-ში **(ვერ დადგინდა)**. ისევე როგორც დღეს, ₾-ს ხატავს სისტემური fallback (Segoe UI / Roboto / SF — ყველა მხარს უჭერს). ფაილს არ ვამატებ: ფასზე `font-variant-numeric: lining-nums`; თუ T27-ის ეკრანზე ₾ ციფრებს სტილით არ ეხამება, ცალკე გადაწყვეტილებაა (მაგ. `latin-ext` subset-იდან მხოლოდ U+20BE) — ამ ტასკში არა.

**ფაილები T27-ისთვის** (ფაილის სახელი ახლანდელი კონვენციით `<family>-<subset>-<weight>.woff2`; `unicode-range` — Google-ის CSS-იდან, როგორც `fonts.css`-ში):
| ოჯახი | subset | წონები | ფაილები |
|---|---|---|---|
| Cormorant Garamond | latin | 400, 500, 600 | 3 |
| Noto Serif Georgian | georgian | 300, 400, 500 | 3 |
| Noto Serif Georgian | latin | 300, 400, 500 | 3 |
| Noto Sans Georgian | georgian + latin | 400, 500, 600, 700 | უკვე 8, არ იცვლება (700 მხოლოდ admin-ს); 300 **არ** ემატება (არც ერთ სტილში არ არის) |
სულ **ახალი 9 woff2**. თუ Google ცვლადი ფაილის ერთ URL-ს აბრუნებს ყველა წონაზე, ფაილი ერთია ოჯახ×subset-ზე (3 ახალი) და `@font-face`-ს `font-weight: 300 600` დიაპაზონი აქვს — მაშინ დადასტურდეს ფაილის ზომა. Cormorant 300/700 და latin-ext არ იტვირთება: hero h1-ის წონა 300 Cormorant-ზე 400-ზე იხსნება (როგორც მოკაპში), ხოლო latin-ext ასოები Noto Serif Georgian-ზე გადავა. `index.html` preload (მაქს. 2): `noto-serif-georgian-georgian-300.woff2` (/ka-ის hero h1) და `noto-sans-georgian-georgian-400.woff2` (ტექსტი).

**სტილები** (desktop ≥ 1024 / მობილური 390; sans თუ სხვა არ წერია; "ლათ." = `/en`-ში იგივე სტილი, ოჯახი იგივე სტეკი):
| სტილი | ოჯახი | desktop | მობილური | წონა | line-height | tracking |
|---|---|---|---|---|---|---|
| display (hero h1) | display | 56px | 34px | 300; გამოკვეთილი სიტყვა 400 + primary-700 | 1.22 | 0 |
| h1 (გვერდი) `(დამატებულია)` | serif | 36px | 28px | 300 | 1.25 | 0 |
| h2 (სექცია) | serif | 34px | 26px | 300 | 1.3 | 0 |
| h3 (ბლოკი, summary) `(დამატებულია)` | serif | 22px | 20px | 400 | 1.35 | 0 |
| title (ბარათის სახელი, კატეგორია) | serif | 18px | 15px | 400 | 1.4 | 0 |
| title-sm (benefit, ფუტერის სათაური) | serif | 15px | 15px | 500 | 1.4 | ფუტერის სათაურზე 0.06em |
| eyebrow | sans | 12px | 12px | 400 | 1.5 | 0.12em; წინ 32×1px ხაზი primary-500 |
| body | sans | 14px | 14px | 400 | 1.6 | 0 |
| lead (აბზაცი hero-ში, info გვერდი) | sans | 15px | 14px | 400 | 1.85 (მობ. 1.8) | 0 |
| small | sans | 12px | 12px | 400 | 1.5 | 0.04em (top bar, copyright) |
| caption (tagline) | sans | 11px | 11px | 400 | 1.4 | 0.06em |
| label (ველის ლეიბლი) `(დამატებულია)` | sans | 13px | 13px | 500 | 1.4 | 0.02em |
| brand label | display, uppercase | 13px | 11px | 600 | 1.3 | 0.3em (მობ. 0.22em); primary-700 |
| price (ბარათი) | display | 26px | 22px | 500 | 1.1 | 0 |
| price sm / lg (PriceTag) | display | 20px / 40px | 18px / 30px | 500 (lg 600) | 1.1 | 0 |
| old price | sans | 15px (md), 12px (sm) | 13px | 400, `line-through`, ink-500 | 1.4 | 0 |
| button | sans | 14px | 14px | 500 | 1 | 0.04em |
| wordmark | display, uppercase CSS | 22px (footer 22) | 17px | 600 | 1 | 0.32em (მობ. 0.26em) |
- `[data-storefront]` ძირი: `font-size: 14px; line-height: 1.6; color: ink-900`; `body`-ზე `transition: background-color .3s, color .3s` (თემის გადართვა; `prefers-reduced-motion` წესი მას აგდებს). admin-ზე არ ვრცელდება.
- ველის ტექსტი `.field-text` უცვლელი: 16px მობილურზე, 14px `sm:`-დან. ციფრები ფასებში/ცხრილში `tabular-nums` (sans), display ფასზე `lining-nums`.
- ქართულზე `uppercase` არ გამოიყენება (ლათინურზე — მხოლოდ wordmark და brand label).

## 4. დაშორებები და layout
- Spacing: Tailwind-ის 4px შკალა; გამოყენებული მნიშვნელობები: 4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 64, 72, 88. კონტროლის სიმაღლე: 46px (header-ის ღილაკები, ძებნა) · 44px (მობილური touch target, `Button md`) · 54px (hero CTA) · 50px (ბარათის CTA desktop; მობ. 44).
- Breakpoints (Tailwind default, უცვლელი): sm 640 · md 768 · lg 1024 · xl 1280 · 2xl 1536; საპროექტო მობილური ბაზა 390px, desktop ≥ 1280.
- კონტეინერი `.container-page`: `max-w-container` = **1368px** (border-box; მოკაპის 1320px კონტენტი + 2×24px), `px-4` (16px) <640, `px-6` (24px) ≥640 (`lg:px-8` იშლება). კონტენტის სიგანე 1440-ზე = 1320px.
- სექციის რიტმი desktop / მობილური (<640): `main` ზედა padding 32 / 20, ქვედა 88 / 56; ბლოკებს შორის 28 / 20; სექცია `padding-top` 48 / 36; სათაურიდან კონტენტამდე 24 / 16; სათაურის ბლოკში eyebrow→h2 8. ფუტერი: padding 72/48 / 48/32, სვეტებს შორის 40 / 32.
- პროდუქტის grid: მთავარი (rows) — 2 სვ. <640 (gap 12), 3 სვ. 640–1023 (gap 16), 4 სვ. ≥1024 (gap 24 → 312px ბარათი 1440-ზე); მობილურზე/ტაბლეტზე row = ჰორიზონტალური `scroll-row` (ბარათი `62vw` / `42vw` sm / `32vw` md, ზუსტად დღევანდელი). კატეგორია/ძებნა (ფილტრის სვეტით 16rem): 2 (<640) → 3 (≥640) → 3 (lg) → 4 (≥1280 `xl`), gap 12 / 16 / 24. Skeleton იგივე სვეტები.
- Sticky: header (top bar-ით) lg-ზე 117px (top bar 40 + header 76 + ხაზები), md–lg 77px, <md 120px (64 + ძებნის რიგი 56). კატეგორიის ფილტრის გვერდითა სვეტის `sticky top` = 8.75rem (140px).
- z-index უცვლელი: header 40 · drawer 50 · modal 60 · toast 70 · skip-link 80.

**მოკაპის ბლოკები 1440 → 390:**
- **Top bar**: 1440 — `canvas` ფონი, 1px `line` ქვევით, `small` ტექსტი ink-500, ორი ჯგუფი (მიწოდება ← → ტელეფონი) `justify-between`, padding 10/24, იკონი 15px primary-500; ტექსტი ისევ `t('header.freeDelivery')` და `CONTACT.phone`. 390 — იმალება (`hidden lg:block`, დღევანდელივით); იგივე ფაქტები მობილურზე ფუტერშია.
- **Header**: 1440 — ფონი `surface`, 1px `line` ქვევით (ბლური/გრადიენტი იშლება), padding 14/24, ერთ რიგში: ლოგო (ნიშანი 46px) · კატეგორიების ღილაკი (46px) · ძებნა (flex-1, მაქს. 36rem) · ენა · თემა (46px წრე) · შესვლა · კალათა (46px წრე), gap 20, მარჯვენა ჯგუფში 4. 390 — რიგი 1 (h 64): მენიუს ღილაკი 44 · ლოგო (ნიშანი 34, wordmark 17px, tagline არა) · თემა · ანგარიში · კალათა (44px, gap 4); რიგი 2 (h 56): ძებნა სრული სიგანე; ენის გადამრთველი მენიუშია (დღევანდელივით).
- **კატეგორიის სვეტი + hero**: 1440 — სვეტი 260px (lg; md 14rem), hero `flex-1`, gap 28; სვეტი `surface` + 1px `line`, ელემენტი padding 14/22, gap 16, იკონი 20px primary-500, ხაზი ელემენტებს შორის `line`. Hero: `surface` + 1px `line`, padding 64 (lg 56, md 40), ტექსტის სვეტი max 520px (eyebrow → display → lead → ორი ღილაკი, gap 26), მარჯვნივ ორნამენტი (§7) მხოლოდ ≥ xl (რადგან ქვემოთ სვეტი hero-ს ავიწროებს; დღევანდელივით). 390 — სვეტი არ არის (drawer); hero padding 28/20, display 34px, lead 14px, ორი ღილაკი ერთმანეთის ქვეშ სრულ სიგანეზე (h 50, gap 12), ორნამენტი არა.
- **Benefits**: 1440 — 4 სვეტი, ზევით და ქვევით 1px `line`, სვეტებს შორის 1px `line`, padding 24/20, იკონი 28px (stroke-fine), `title-sm` + small ink-500. 390 — 2 სვ., იკონი ტექსტის თავზე (column), padding 16/14, ხაზები უჯრის საზღვრებით.
- **Popular categories**: 1440 — სექცია: h2 + ქსელი `lg:grid-cols-6` (მოკაპში 5 უჯრა 264px); უჯრა: `surface`, padding 36/18, ცენტრში 70px რომბი-ჩარჩო + იკონი, `title` 17px, count `small` ink-500; **ქსელის ხაზი უჯრის საზღვრებით** (`border-t border-l` კონტეინერზე, `border-r border-b` უჯრაზე) და არა `gap:1px` + ფონი — წინააღმდეგ შემთხვევაში არასრული რიგი `line`-ფერ ცარიელ უჯრებს აჩენს. 390 — 2 სვ. (640+: 3), padding 24/12, რომბი 56px.
- **Product row**: 1440 — h2 მარცხნივ, მარჯვნივ ორი 46px წრიული ღილაკი (prev: საზღვარი `outline`; next: საზღვარი primary-500, იკონი primary-700), მხოლოდ ≥ lg (დღევანდელივით); ქვეშ 4 სვ. grid. 390 — ღილაკები არა; `scroll-row` swipe, ბარათი `62vw`.
- **Footer**: 1440 — ფონი `footer`, 1px `line` ზევით, 4 სვეტი (ბრენდი + აღწერა + "უფასო მიწოდების" ეტიკეტი | კატეგორიები | ინფორმაცია | კონტაქტი), სათაური `title-sm` primary-700, ბმული ink-500 (hover primary-700), კონტაქტის იკონი 16px primary-500; ქვედა ზოლი 1px `line` + `small` ink-500. 390 — 1 სვეტი (640+: 2), ბრენდის ბლოკი პირველი.

## 5. ფორმები: რადიუსი, ჩრდილი, იკონი, საზღვარი, მოძრაობა
ახალი თემის ტოკენები CSS ცვლადებია (`:root` = admin, `.theme-light` / `.theme-dark`, `[data-admin]` და `:root:has([data-admin])` აბრუნებს admin-ს) — იგივე მექანიზმი, რაც ფერს; Modal/Toast პორტალში `<html>`-იდან კითხულობენ.
| ტოკენი | admin (დღევანდელი) | light | dark |
|---|---|---|---|
| `rounded-control` (ღილაკი, input, ტეგი) | 0.625rem | 2px | 2px |
| `rounded-card` (ბარათი, toast, მოდალი, panel) | 0.875rem | 0 | 0 |
| `rounded-pill` (წრიული ღილაკი, count, chip) | 9999px | 9999px | 9999px |
| `shadow-card` | `0 1px 2px 0 rgb(18 21 29 / 0.04), 0 1px 3px 0 rgb(18 21 29 / 0.06)` | `none` | `none` |
| `shadow-card-hover` და `shadow-glow` (ბარათის hover) | card-hover: `0 10px 24px -6px rgb(18 21 29 / 0.14), 0 2px 6px -2px rgb(18 21 29 / 0.08)`; glow: `0 0 0 1px rgb(var(--c-primary-400) / 0.25), 0 14px 36px -14px rgb(var(--c-primary-600) / 0.6)` | ორივე: `0 0 0 1px rgb(var(--c-primary-500) / 0.45), 0 14px 32px -18px rgb(60 48 30 / 0.25)` | ორივე: `0 0 0 1px rgb(var(--c-primary-500) / 0.4), 0 18px 40px -18px rgb(0 0 0 / 0.8)` |
| `shadow-popover` (flyout, toast, მოდალი, dropdown) | `0 12px 32px -8px rgb(18 21 29 / 0.22), 0 4px 10px -4px rgb(18 21 29 / 0.10)` | `0 18px 40px -14px rgb(60 48 30 / 0.28), 0 2px 8px -2px rgb(60 48 30 / 0.12)` | `0 20px 48px -12px rgb(0 0 0 / 0.75), 0 0 0 1px rgb(var(--c-ink-200))` |
| `shadow-header` | `0 1px 0 0 rgb(18 21 29 / 0.06)` | `none` | `none` |
| `shadow-btn` (ახალი; ღილაკის `shadow-sm`) | `0 1px 2px 0 rgb(0 0 0 / 0.05)` | `none` | `none` |
| `--icon-stroke` (`.lucide { stroke-width }`) | 2 | 1.4 | 1.4 |
| `--icon-stroke-fine` (ახალი; ≥ 24px ორნამენტული იკონი: benefit, კატეგორია, class `icon-fine`) | 2 | 1.1 | 1.1 |
| `--btn-weight` / `--btn-tracking` (ახალი) | 600 / 0 | 500 / 0.04em | 500 / 0.04em |
- ბარათი: 1px `line` საზღვარი, ჩრდილი არა. ტექსტური ველი, checkbox/radio, stepper-ის ჩარჩო: 1px `line-strong` (ink-300); ღილაკის/წრიული იკონ-ღილაკის კონტური: 1px `outline`. ხაზები ყველგან 1px, ორნამენტული ხაზი (eyebrow-ის) 1px primary-500.
- მოძრაობა უცვლელი: fade-in 180ms, slide-up 220ms, sheet-up/slide-in 260ms, badge-pop 420ms, shimmer 1.6s, `transition-colors` 150ms; ბარათის hover 200ms. `prefers-reduced-motion` ყველაფერს ≈0-მდე ასუსტებს (არ იცვლება). ახალი: body-ს 300ms თემის გადასვლა (მოკაპი) — ამავე წესით გამორთვადია. ბარათის `-translate-y-0.5` hover იშლება (მოკაპი სტატიკურია).
- გლობალურ `:focus-visible`-ს `rounded-sm` ჩამოშორდეს storefront-ში (წრიული ღილაკი ფოკუსზე კვადრატი გახდებოდა); admin-ში დარჩეს (`[data-admin] :focus-visible { rounded-sm }`).

## 6. კომპონენტები და მდგომარეობები
საერთო წესი ყველა მდგომარეობაზე (თუ არ წერია სხვა): **hover** — ხაზოვანი კონტროლი: საზღვარი primary-500 + ფონი primary-50; უბორდერო იკონ-ღილაკი: ფონი ink-100; ტექსტური ბმული: ფერი primary-700 (+ underline ტექსტში); **active** — ფონი primary-100; **focus-visible** — `ring-2 ring-primary-500 ring-offset-2 ring-offset-surface` (§2.3), ყველა თემაში ხილული; **disabled** — §2.3, `cursor-not-allowed`; **loading** — `Loader2 h-4 w-4 animate-spin`, `disabled` + `aria-busy`, ლეიბლი რჩება; **error** — საზღვარი danger-500, ტექსტი danger-fg + `AlertCircle`. იკონი 16px (ღილაკი/ველი), 18px (header), 20px (toast, ბარათის ლისტი); `aria-hidden="true"`; იკონ-ღილაკს `aria-label` აქვს.

**Top bar** — §4. ბმული (ტელეფონი) hover → primary-700. **Header** — §4; sticky, ფონი surface. **კატეგორიების ღილაკი**: h 46, საზღვარი `outline`, ფონი გამჭვირვალე, რადიუსი 2px, რომბის იკონი 16px primary-500 + ლეიბლი + chevron 14px; hover/active/focus — საერთო წესი; ღია flyout-ზე `aria-expanded`, ღილაკს ფონი primary-50. **Flyout**: `surface`, 1px `line`, `shadow-popover`, ელემენტი padding 14/22, ხაზები `line`; hover/არჩეული ფონი primary-50, ტექსტი ink-900; ქვეკატეგორია 14px ink-700. **ძებნა**: მხოლოდ ქვედა ხაზი (1px ink-300 — ველის ერთადერთი საზღვარი, ამიტომ AA 3:1; h 46), ლუპა 18px ink-500, placeholder ink-500; focus-within — მთელ რიგს standard focus ring; **suggestions**: popover (surface, 1px line, shadow-popover), ელემენტი 14px, hover/აქტიური primary-50, ნაპოვნი ნაწილი 500, ჯგუფის სათაური `small` ink-500. **ენა**: გლობუსი 18px + მიმდინარე ენის კოდი, უბორდერო, h 46 px-12; hover ფონი ink-100. **თემის გადამრთველი**: 46px წრე, საზღვარი `outline`, იკონი primary-500 (light-ში მთვარე, dark-ში მზე), hover საერთო; `aria-label` უცვლელი. **User menu**: უბორდერო ტექსტ+იკონის ღილაკი h 46 (ლეიბლი ≥ lg); dropdown = popover, ელემენტი h 44, hover primary-50, გასვლა — ტექსტი danger-fg, hover ფონი danger-50. **კალათა**: 46px წრე, ფონი primary-600, იკონი on-primary; hover `primary-hover`, active `primary-press`; count ბეჯი: pill min 20px, ფონი accent-600, ტექსტი white (4.93), `ring-2 ring-surface`, `badge-pop` უცვლელი. **Mobile menu** (`Modal position=left`): სიგანე min(85vw, 340px), `surface`, header: ლოგო + დახურვა (icon-ღილაკი 44), ელემენტი h 52 + ქვედა 1px line, scrim `/50`.

**ღილაკი** (`Button.jsx`; admin-იც იყენებს — ფორმა/რადიუსი/წონა/ჩრდილი მხოლოდ ტოკენებით: `rounded-control`, `shadow-btn`, `--btn-weight`, `--btn-tracking`). ზომები (admin-ისთვის უცვლელი): xs h-8 px-3 text-xs · sm h-9 px-3.5 text-sm · md h-11 px-5 text-sm · lg h-12 px-6 text-base · icon 40×40; **ახალი opt-in** `xl`: h 54, px 30, text-sm, gap 14 (hero CTA); storefront-ის 46px icon-ღილაკი — `icon` + `rounded-pill` (header-ის კომპონენტებში, არა `Button`-ში). ვარიანტები (light / dark ფერი role-ით):
- **primary**: `bg-primary-600 text-on-primary`; hover `primary-hover`; active `primary-press`; disabled `primary-300`. light: მუქი #1C1B19 + კრემი; dark: ოქრო + #0E0E0F.
- **secondary**: `bg-ink-900 text-surface` (light მუქი, dark კრემისფერი); hover ink-800; active ink-950; disabled ink-400.
- **outline**: `border-outline bg-surface text-ink-800` (admin-ზე `outline` = #c2c9d6 = დღევანდელი `border-ink-300`; hero CTA-ზე `xl`); hover საზღვარი primary-500, ფონი primary-50, ტექსტი primary-700; active primary-100; disabled ტექსტი ink-400, საზღვარი ink-200.
- **ghost**: `text-ink-700`; hover ink-100 + ink-900; active ink-200; disabled ink-400.
- **link**: `text-primary-700`, hover underline (offset 4); disabled ink-400.
- **danger**: `bg-danger-600 text-white`; hover/active danger-700; disabled `danger-500/50`.
- **accent** (admin-ის "პირველადი"; storefront-ზე არ გამოიყენება): უცვლელი.
- **icon**: ghost ან outline + კვადრატი/წრე; სიმაღლე 44 მობილურზე.
`text-white` მხოლოდ accent/danger ფონზე; primary ფონზე — `text-on-primary`; skip-link: `bg-primary-600 text-on-primary`.

**Input / Select / Textarea** (shared): h 44 (textarea min-h 112), `rounded-control border border-ink-300 bg-surface px-3.5 text-ink-900`, placeholder ink-500; hover საზღვარი primary-500; focus საზღვარი primary-500 + `ring-2 ring-primary-500/30` (+ გლობალური ring არა — ფარავს ეს); error საზღვარი danger-500 + `ring-danger-500/30`, ქვემოთ `AlertCircle` 16 + `small` 500 danger-fg, `aria-invalid`/`aria-describedby`; hint `small` ink-500; disabled ფონი ink-100, ტექსტი ink-500, საზღვარი ink-200; loading — ველის მარჯვნივ 16px spinner. ლეიბლი `label` სტილი ink-800, `*` danger-fg. Select — chevron 16px ink-500, native `<select>`. **Checkbox/radio**: 18px, საზღვარი ink-300, ფონი surface, რადიუსი 2px (radio წრე); checked ფონი primary-600, ნიშანი on-primary; focus ring; disabled ინკ-100 ფონი. **Quantity stepper**: h 44 (sm 36), 1px ink-300, ორი ghost icon-ღილაკი 44×44 + რიცხვი `tabular-nums` ცენტრში (ორ საზღვარს შორის 1px line), disabled მხარეს ink-400. **Price slider**: ბილიკი 4px ink-200, არჩეული მონაკვეთი primary-600, thumb 18px წრე, საზღვარი 2px primary-600, ფონი surface, focus ring; ორი რიცხვითი ველი h 36 (`.field-text` რჩება) + `₾` ink-500. **Filter group**: სათაური `title-sm` (serif 15/500), ქვედა 1px `line`, checkbox-ები gap 10, count `small` ink-500 მარჯვნივ; აქტიური ფილტრი chip: pill, ფონი primary-50, ტექსტი primary-800, ×-ღილაკი; ფილტრების ღილაკი მობილურზე outline sm + count pill (primary-600/on-primary). **Sort**: Select h 40. **Pagination**: ღილაკი 40×40 (რიცხვი/იკონი ლეიბლია), 1px `outline`, რადიუსი 2px; მიმდინარე გვერდი ფონი primary-600 + on-primary (`aria-current`); hover საერთო; disabled prev/next ტექსტი ink-400, საზღვარი ink-200. **Breadcrumbs**: `small` ink-500, გამყოფი chevron 12px ink-400, მიმდინარე ink-900/500, ბმული hover primary-700 + underline.

**Badge** (`Badge.jsx`, რადიუსი 2px, `font-semibold`, text-2xs/xs, tracking 0.04em, padding 3/8): new — `bg-primary-600 text-on-primary` · discount — `bg-accent-600 text-white` · danger/out-of-stock — `bg-ink-900 text-surface` · success — `bg-success-50 text-success-700` + `ring-1 ring-success-500/25` · warning — `bg-warning-50 text-warning-600` + `ring-1 ring-warning-500/30` · neutral — `bg-ink-100 text-ink-700` · outline — `bg-surface text-ink-700 ring-1 ring-ink-300`. Stock badge — იკონი 14 + ტექსტი.

**პროდუქტის ბარათი**: `surface`, 1px `line`, რადიუსი `card` (0), `overflow-hidden`; ფოტოს ფილა სრული სიგანე, `aspect-square`, `bg-media`, padding-ის გარეშე; ფილის ქვეშ 1px `line`; ბეჯები ფილაზე top-left 12/12 (ვერტიკალური, gap 6); ტექსტის ბლოკი padding 22 (მობილური 14), gap 8: brand label → `title` (2 ხაზი, `min-h` 2.5rem) → description `small` ink-500 (2 ხაზი) → rating → ფასი (`mt-auto`) → CTA (`lg`, სრული სიგანე, მობ. md). ბარათი მთლიანი ბმულია (დღევანდელივით). Hover: საზღვარი → `shadow-glow` (primary-500 ორნამენტული 1px), სახელი → primary-700, სურათი scale 1.04 (300ms). CTA მდგომარეობები: default primary (კალათის იკონი 16 + ტექსტი); კალათაში — `bg-success-50 text-success-700 ring-1 ring-success-500/30`, hover success-100; out-of-stock — disabled, ტექსტი ink-500 ფონი ink-100; ფილაზე out-of-stock ფენა `bg-white/70` + pill `bg-scrim/85 text-white`. Loading = ProductCardSkeleton იგივე გეომეტრიით. **ფასი**: display 500; ძველი ფასი sans `line-through` ink-500; დაზოგვა `small` 500 accent-fg; discount ბეჯი accent-600. **Rating stars**: ვარსკვლავი 14px (`md` 18), შევსებული `accent-400`, ცარიელი ink-300, რაოდენობა `small` ink-500. **Gallery**: მთავარი სურათი — იგივე ფილა (`media`, 1px line, `aspect-square`), thumbnails 64px ფილა 1px line, არჩეული 2px primary-500, hover საერთო, focus ring.

**Cart line**: რიგი border-b `line`, padding 20; ფილა 88px (მობ. 72) 1px line; სახელი `title`; ფასი display 500 20px; stepper + წაშლის ghost icon-ღილაკი (hover ფონი danger-50, ტექსტი danger-fg); მობილურზე ფასი და stepper ახალ ხაზზე. **Summary**: `surface` + 1px `line`, padding 24, `h3`; რიგები `body` justify-between, `line` გამყოფი; ჯამი display 600 30px; CTA lg სრული სიგანე; sticky `top-[8.75rem]` ≥ lg. **Modal**: panel `surface`, 1px `line`, `rounded-card`, `shadow-popover`, სათაური border-b px-5 py-4 (sans 16/600 — Modal admin-თან საერთოა), ფონი `bg-scrim/50`, ESC/focus trap უცვლელი. **Toast**: `surface`, 1px `line` + მარცხნივ 3px ზოლი სტატუსის ფერით (success-600 · danger-500 · primary-500), `rounded-card`, `shadow-popover`, იკონი 20 (`CheckCircle2` success-600 · `AlertCircle` danger-fg · `Info` primary-700), ტექსტი 14/500, ქმედება primary-700 600; `aria-live="polite"`. **Delivery table**: 1px `line`, `rounded-card`, thead ფონი ink-100 ტექსტი ink-700 600 13px tracking 0.04em, რიგები `divide-line`, ბოლო რიგი ფონი primary-50 ტექსტი primary-800, ციფრი `tabular-nums` მარჯვნივ. **Empty / error / loading**: §9.

## 7. ლოგო და favicon
**ნიშანი** (ბრენდის ერთადერთი ხელით დახატული SVG, `Logo.jsx` ექსპორტს უკეთებს `Mark`-ს ფუტერისა და hero-სთვის; ფერი `currentColor` ← `text-primary-500`; stroke 2 (მოკაპის 1.5 ≤ 46px-ზე ქრება), შიდა რომბი 0.45 opacity):
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 70 70" width="46" height="46" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true">
  <path d="M35 3 67 35 35 67 3 35z"/>
  <path d="M35 10 60 35 35 60 10 35z" stroke-opacity=".45"/>
  <path d="M38 21l-11 16h8l-3 12 11-16h-8l3-12z"/>
</svg>
```
**Wordmark**: `SITE_NAME` (VoltBox) ტექსტად (`aria-label` ბმულზე უცვლელი), `font-display`, წონა 600, CSS `uppercase` → VOLTBOX, `letter-spacing: 0.32em`, `line-height: 1`, ფერი ink-900; tagline (`site.tagline`, caption 11px ink-500, 4px ქვემოთ) მხოლოდ ≥ lg. ნიშანი და ტექსტი gap-ში (flex, ცენტრი). ბოლო ასოს შემდეგ tracking-ის ზედმეტ სივრცეს `margin-right: -0.32em` აგდებს.
| ადგილი | ნიშანი | wordmark | gap |
|---|---|---|---|
| header ≥ md | 46px | 22px / 0.32em | 14px |
| header < md | 34px | 17px / 0.26em | 10px |
| footer ≥ sm | 50px | 22px / 0.32em | 14px |
| footer < sm | 40px | 20px / 0.28em | 12px |
| hero ორნამენტი (≥ xl) | 96px ცენტრში | — | — |
**Hero ორნამენტი** (`aria-hidden`, სიტყვების გარეშე): 340px წრე `glow` gradient `radial-gradient(circle at 50% 45%, rgb(var(--c-glow)) 0%, rgb(var(--c-primary-50)) 45%, rgb(var(--c-primary-50) / 0) 70%)`; მასზე 300px ორმაგი რომბი `stroke-width .25` (ანუ ≈1px), `stroke-opacity .7 / .35`, ფერი primary-500; ცენტრში `Mark` 96px.
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 70 70" width="300" height="300" fill="none" stroke="currentColor" stroke-width=".25" aria-hidden="true">
  <path d="M35 3 67 35 35 67 3 35z" stroke-opacity=".7"/>
  <path d="M35 10 60 35 35 60 10 35z" stroke-opacity=".35"/>
</svg>
```
**Favicon** (`public/favicon.svg`, ფიქსირებული ფერები): ამოვსებული ოქროს რომბი მუქი 1.5 კონტურით (ღია tab-ზე კონტური 17:1, მუქ tab-ზე ოქრო ≥ 6:1) + ამოვსებული ბოლტი (თხელი შიდა რომბი და 1.5 stroke 16px-ზე ქრება, ამიტომ მოხსნილია; ბოლტი 62% სიმაღლისაა, 16px-ზე 10px):
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <path d="M16 1.5 30.5 16 16 30.5 1.5 16z" fill="#C9A96E" stroke="#1C1B19" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M18 6 9 18h6l-2 8 10-13h-6z" fill="#1C1B19"/>
</svg>
```
ბოლტი/ოქრო 7.69:1. (`og-image.png` და PNG იკონები ძველი რჩება — Open Questions.)

## 8. სურათები და იკონები
- იკონები: **lucide-react** (MIT), სხვა ნაკრები არ არის; სისქე მხოლოდ ტოკენით (§5); ფერი: ორნამენტული/კატეგორიის/top bar-ის — primary-500, ფუნქციური (ღილაკი, ველი, nav) — `currentColor`. კატეგორიის იკონი: `CategoryIcon` 28px (`icon-fine`) 70px რომბ-ჩარჩოში (ორნამენტული `aria-hidden` SVG, `M35 2 68 35 35 68 2 35z`, stroke .8, opacity .6, primary-500; hover opacity 1).
- **პროდუქტის ფოტოს ფილა** (Decision Log 2026-10-19: ორივე თემაში ღია): `media` #F5F1E9, ფოტო `object-cover` + `storefront:mix-blend-multiply` (თეთრი ფონი ფილას ერწყმის), ჩარჩოს რადიუსი 0, ფილაზე ჩრდილი არა; loading — `media-shade/60` pulse. dark თემაშიც ფილა ღიაა (ბარათის კიდიდან კიდემდე, 1px `line` ქვევით).
- **ფოტოს არქონა**: ფილა იგივე; ნახატი — მოკაპის სურათის იკონი ink-400-ით. `public/images/placeholder.svg` admin-საც ჩანს, ამიტომ **არ იცვლება**; storefront-ისთვის ახალი ფაილი `public/images/placeholder-shop.svg` (opt-in prop `ProductImage`-ზე, admin არ გადასცემს), ფონის გარეშე (ფილა იძლევა), ხატი ≈20% ფილისა, stroke #8C8474 (ფილაზე 3.29:1; ეს ფიქსირებული hex ფაილშია, რადგან `<img>` ცვლადს ვერ კითხულობს; dark თემაშიც იგივე, რადგან ფილა იგივეა), იგივე `aria-label`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-48 -48 120 120" role="img" aria-label="სურათი მიუწვდომელია">
  <g fill="none" stroke="#8C8474" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M3 4h18v16H3zM7 9.5a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0-3 0M21 16l-5-5L5 20"/>
  </g>
</svg>
```
- `frontend/public/images/placeholder-shop.svg` არის **ახალი ფაილი**, რომელსაც ქმნის ის ტასკი, ვისაც `ProductImage` ეკუთვნის (T32); planner-მა ფაილების სიაში უნდა ჩაწეროს.
- ფოტო პროდუქტის გვერდზე — იგივე ფილა; ეკრანზე ფოტოსთვის alt = პროდუქტის სახელი (უცვლელი).

## 9. გვერდის მდგომარეობები
- **Loading**: `Skeleton` (`bg-ink-200/70`, shimmer 1.6s `via-surface/60`), რადიუსი ელემენტის; ბარათის skeleton = ბარათის იდენტური გეომეტრია (ფილა სრულ სიგანეზე, 1px line, `rounded-card`); spinner მხოლოდ ღილაკში. ჩატვირთვის ტექსტი `small` ink-500 (`aria-live="polite"`). `PageFallback`: breadcrumb-ის ზოლი (h 16, w 208) → სათაური (h 32, w 288) → 8 ბარათის skeleton grid — იგივე კონტეინერი, `role="status"`.
- **Empty** (`EmptyState`): `rounded-card border border-dashed border-ink-300 bg-surface px-6 py-14 text-center`; 64px წრე `bg-ink-100`, იკონი 28px ink-500 (`--icon-stroke`); სათაური 18/600 sans (shared admin-თან), აღწერა 14 ink-600, მოქმედება primary `Button`.
- **Error** (`ErrorState`): `role="alert"`, `rounded-card border border-danger-100 bg-danger-50 py-12 text-center`, `AlertTriangle` danger-fg 56px წრეში `bg-danger-100`, სათაური ink-900, ტექსტი ink-700, outline "ხელახლა" ღილაკი. field error — §6.
- **Error boundary** (მთელი აპი, router-ის გარეთ, shared admin-თან): ეკრანი `bg-ink-50`, ბარათი `max-w-md rounded-card border border-ink-200 bg-surface p-8 text-center shadow-card` (storefront-ში ჩრდილი არა, კუთხე 0), `AlertOctagon` danger-fg 28px წრეში `bg-danger-50`, h1 20px/700 sans (შრიფტი არ იცვლება — shared admin-თან), ტექსტი ink-600, ღილაკი სრული სიგანე primary (`text-on-primary`). ლოგო/Link არ ემატება (router არ არის).

### 9.1 გვერდების გზამკვლევი (მოკაპი ამ გვერდებს არ აჩვენებს; სტრუქტურა დღევანდელია, იცვლება მხოლოდ იერი)
საერთო: გვერდის კონტეინერი `container-page py-5 lg:py-7`; breadcrumb-ი ზემოთ (`mb-4`); h1 — სტილი `h1`, ქვეშ 1px `line`-ის გარეშე; ბლოკები `surface` + 1px `line` + 0 რადიუსი, padding 24 (მობ. 16); ფორმის ველებს შორის 16; ყველა ღილაკი §6; ფასი display.
- **Category და Search**: header — h1 + აღწერა `body` ink-600; მარცხნივ ფილტრის სვეტი ≥ lg (16rem, `surface`, 1px `line`, padding 16, `sticky top-[8.75rem]`), მობილურზე "ფილტრები" outline sm → bottom sheet (`Modal position=bottom`); ზოლი: "ნაპოვნია N" `body` + Sort; აქტიური ფილტრების chip-ები; grid §4; Pagination ქვემოთ `mt-8` ცენტრში; ცარიელი შედეგი — `EmptyState`. Search: h1 ძებნის ტექსტით, იგივე grid.
- **Product**: ორი სვეტი ≥ lg (gallery | ინფო, gap 40): brand label → h1 (`h1`) → rating+stock badge → აღწერა `lead` → ფასის ბლოკი (`surface` + 1px line, padding 24: ფასი lg, ძველი ფასი, discount ბეჯი, დაზოგვა accent-fg, stepper + `lg` primary "კალათაში დამატება") → 4 ფაქტის სია (იკონი 16 primary-500); ქვემოთ tabs: ზოლი border-b `line`, ტაბი `button` 14/500, აქტიური — ქვედა 2px primary-600 + ტექსტი ink-900, სხვა — ink-600, hover primary-700; პანელი padding 24; მახასიათებლების ცხრილი: რიგები `divide-line`, key ink-500, value ink-900; ქვემოთ "მსგავსი" row.
- **Cart**: h1 + მარცხნივ რიგები (Cart line), მარჯვნივ Summary (≥ lg 360px, sticky); ცარიელი — `EmptyState`; მობილურზე Summary რიგების ქვემოთ. 
- **Checkout**: ორი სვეტი (ფორმა | summary), ფორმა — ბლოკები `h3` სათაურით (ნომრის გარეშე), ველები Input/Select/Textarea; მიწოდების/გადახდის არჩევა — radio ბარათები (1px ink-300, არჩეული საზღვარი primary-500 2px + ფონი primary-50); შეცდომა — ველის ქვეშ + ზედა `role="alert"` ბლოკი (`border-danger-100 bg-danger-50 text-danger-fg`); submit `lg` loading-ით.
- **Order confirmation**: ცენტრში max-w 640 ბარათი: ზევით ორნამენტული რომბი-ჩარჩო (§8) `CheckCircle2` success-600 28px, h1 (ცენტრი), შეკვეთის ნომერი display 500 24px, შეკვეთის რიგები `surface` ბლოკში, ღილაკები primary + outline.
- **Login / Register / Forgot / Reset**: ცენტრირებული ბარათი max-w 448 (`surface`, 1px line, padding 32/24), ლოგოს ნიშანი (`Mark` 48px primary-500) ზემოთ, h1 `h1` 28px, ველები სრული სიგანე, primary `lg` ღილაკი, მეორადი ბმულები `small` primary-700 underline; შეცდომა/წარმატება — ბანერი (danger-50/danger-fg ან success-50/success-700, `role="alert"`/`status`). Mock-auth შენიშვნა (მხოლოდ mock build-ში) — `small` ink-500.
- **Account** (Layout, Orders, Profile, Addresses, Password): ≥ md მარცხნივ ნავიგაცია 14rem (`surface`, 1px line; ელემენტი h 44 px-16, აქტიური — ფონი primary-50 + მარცხნივ 2px primary-500 + ტექსტი ink-900/500, hover ink-100), მობილურზე ჰორიზონტალური გადასარევი ტაბები; Orders — ბარათების სია (ნომერი display, თარიღი `small`, სტატუსი Badge tone-ით `ORDER_STATUS_TONES`, ჯამი display, ბმული "დეტალები"); Profile/Password — ფორმა max-w 480 ბლოკში; Addresses — ბარათები grid 1/2 სვ., ძირითადი მისამართი Badge outline, ქმედებები ghost sm; ცარიელი — `EmptyState`.
- **Info გვერდები** (delivery, returns, privacy, FAQ, contact): h1 + პროზა max-w 720: h2 serif 24/300, აბზაცი `lead` ink-700 (9.09:1), სიები ორნამენტული 4px რომბი (primary-500) მარკერად, ბმული primary-700 underline. **Delivery table** — §6. **FAQ**: `details` რიგები border-b `line`, summary h 56 `title` + chevron 16 (ღია — 180° ბრუნვა), პასუხი `lead` ink-700, focus ring.
- **404**: ცენტრში `Mark` 96px primary-500, h1 `h1`, არსებული ტექსტი და ღილაკი primary (`to="/"`); ახალი ტექსტი არ ემატება.
- **Loading fallback** და **Error boundary** — §9.

---

# Admin panel (frozen)
ეს სექცია გადმოტანილია წინა DESIGN.md-დან ცვლილების გარეშე (განსხვავებულია მხოლოდ სათაურების ნუმერაცია). admin-ი ყოველთვის light-ია, `data-admin` აბრუნებს admin-პალიტრას, და მისი იერი არ იცვლება; storefront-ის ახალი ტოკენების admin მნიშვნელობა = ქვემოთა/დღევანდელი (იხ. §2.2, §5).

## A.1 მიმართულება
ტექნიკის მაღაზია: სუფთა, ნეიტრალური ცივი-ნაცრისფერი (ink) ზედაპირები, ერთი ლურჯი `primary` ინტერაქციისთვის, ნარინჯისფერი `accent` — storefront-ზე მხოლოდ ფასს/ფასდაკლებას. Storefront-ს აქვს light და dark თემა; ადმინ-პანელი "გაყინულია" და ყოველთვის light-ია. ვერიდებით ფერის ერთადერთ სიგნალად გამოყენებას (სტატუსი = ტექსტი + ფერი) და `dark:` კლასებს (თემა = პალიტრის ცვლადები).

## A.2 ფერები (admin)
Tailwind-ში ფერი როლით იწოდება და CSS ცვლადზე (`--c-<name>-<step>`) იხსნება. თემა: `:root` = admin; `[data-admin]` (და `:root:has([data-admin])`) აბრუნებს admin-ს. ქვემოთ მნიშვნელობები **admin**.

| როლი (კლასი) | admin |
|---|---|
| გვერდის ფონი `canvas`=ink-50 | #f7f8fa |
| ზედაპირი `surface` (ბარათი, input, მოდალი) | #ffffff |
| ამაღლებული ფონი/hover `ink-100` | #eef0f4 |
| გამყოფი `line`=ink-200 (დეკორატიული) | #dde1e9 |
| კონტროლის საზღვარი `line-strong`=ink-300 | #c2c9d6 |
| იკონები/გამყოფი ink-400 | #97a1b5 |
| მეორადი ტექსტი `fg-muted`=ink-500 | #657086 |
| ტექსტი ink-600 / 700 / 800 | #56617a / #454e63 / #333a4a |
| ძირითადი ტექსტი `fg`=ink-900 | #1e2330 |
| primary-50 / 100 (ტინტი) | #eef3ff / #dbe5ff |
| primary-500 (focus, საზღვარი) | #3a5bf5 |
| primary-600 `primary` (solid fill) | #2440e0 |
| primary-hover / press | #1e33bd / #1d2f99 |
| primary-700 (ტექსტი ზედაპირზე/ტინტზე) | #1e33bd |
| accent-600 `accent` (ფასი, ფასდაკლება) | #c74407 |
| accent-700 / 800 | #9e360e / #7f2e0f |
| accent-50 | #fff8ed |
| success 50 / 600 / 700 | #ecfdf5 / #059669 / #047857 |
| danger-50 / 100 | #fef2f2 / #fee2e2 |
| danger-500 (შეცდომის საზღვარი) / 600 / 700 | #ef4444 / #dc2626 / #b91c1c |
| `danger-fg` (შეცდომის ტექსტი) | #dc2626 |
| warning-50 / 500 / 600 (ტექსტი) | #fffbeb / #f59e0b / #aa5d05 |
| `media` (ფოტოს ფილა, ყველა თემაში) | #eef0f4 (`media-shade` #dde1e9) |
| `scrim` (მოდალის ფონი, `/50`) | #12151d |

ხატვის წესი: ტექსტი/ფონი ყოველთვის როლით (`text-ink-900`, `bg-surface`), hex-ი კომპონენტში არ იწერება. `src/utils/palette.test.js` ამოწმებს storefront-ის წყვილებს AA-სთვის ორივე თემაში.

### კონტრასტი (WCAG ფორმულით გამოთვლილი, ხელით)
Admin (light): ink-900 / canvas **14.76:1**; ink-900 / white **15.69:1**; ink-600 / white **6.20**, / canvas **5.83**; ink-500 / white **4.98**, / canvas **4.69**, / ink-100 **4.37 (< 4.5)**; ink-700 / white 8.32, / ink-100 7.29.
Ღილაკები (admin = light): ტექსტი white on primary-600 **7.28**; on primary hover **9.28**; white on accent-600 **4.93**, accent-700 **7.03**; white on danger-600 **4.83**, danger-700 **6.47**; secondary (white on ink-900) **15.69**, hover ink-800 **11.38**; outline ink-800 / white **11.38**.
ბეჯები/ბანერები: danger-700 / danger-50 **5.92**; warning-600 / warning-50 **4.74**; success-700 / success-50 **5.21**; primary-700 / primary-50 **8.35**; accent-800 / accent-50 **8.65**; ink-700 / ink-100 **7.29**; danger-600 / danger-50 (admin `danger-fg`) **4.41 (< 4.5)**.
არა-ტექსტური: focus ring primary-500 `#3a5bf5` / white ≈ 5.5 (>3:1; მხოლოდ შეფასება, ზუსტად არ გამომითვლია). Admin control-border ink-300 / white **1.66 (< 3:1)**; ink-400 icon / white **2.60** — იხ. nits.
ვერ დადგინდა: disabled მდგომარეობების კონტრასტი (WCAG-ით გათავისუფლებულია; `primary-300` + white ≈ 2.1).

## A.3 ტიპოგრაფია (admin)
- ოჯახი (`font-sans`): `"Noto Sans Georgian", Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`. Noto Sans Georgian self-hosted (`/fonts/*.woff2`, `font-display: swap`), ქართული + ლათინური subset, წონები 400/500/600/700, `unicode-range` ორივე დამწერლობისთვის. ქართულის მხარდაჭერა: **კი** (Noto Sans Georgian; დასტური `fonts.css`-იდან: georgian subset-ის ფაილები და `unicode-range` U+10A0–10FF, მთავრული U+1C90–1CBF; WebSearch-ით არ გადამიმოწმებია). Inter არ იტვირთება (მხოლოდ სიაშია); fallback-ების (Roboto, Arial, Helvetica Neue) ქართული დაფარვა **ვერ დადგინდა**; system-ui/Segoe UI ჩვეულებრივ აფარებს. ლიცენზია: SIL OFL (Google Fonts; კოდში არ წერია).
- ზომები (Tailwind default + `2xs`): 2xs 11/16px · xs 12/16 · sm 14/20 · base 16/24 · lg 18/28 · xl 20/28 · 2xl 24/32 · 3xl 30/36 · 4xl 36/40 · 5xl 48/1.
- ველის ტექსტი (`.field-text`): 16px მობილურზე, 14px `sm:`-დან (iOS zoom-ის გამო; `maximum-scale` აკრძალულია).
- Admin h1: `text-lg font-semibold text-ink-900`; ქვესათაური `text-sm text-ink-600`; სექციის h2 `text-sm font-semibold`; ცხრილის th `text-xs font-medium uppercase tracking-wide text-ink-500`; რიცხვები `tabular-nums`.
- Weights: 400 ტექსტი, 500 ლეიბლი/ბეჯი, 600 ღილაკი/სათაური, 700 h1.

## A.4 დაშორებები და layout (admin)
- Spacing: Tailwind-ის 4px შკალა (1=4px … 4=16px, 6=24px). ბარათის padding `p-4`/`p-3.5 sm:p-4`; admin სექცია `p-4`, გვერდი `p-4 md:p-6`; ბლოკებს შორის `space-y-4`, ფილტრებს `gap-2`.
- Breakpoints (Tailwind default, არ არის გადაწერილი): sm 640 · md 768 · lg 1024 · xl 1280 · 2xl 1536. მობილური ბაზა ≈390px.
- Admin: sidebar `w-56` (`md:` და ზევით; ქვემოთ დამალულია — მობილური ნავიგაცია ადმინში **არ არის**), header `h-14`, `main` `min-w-0 flex-1`; ორსვეტა დეტალი `lg:grid-cols-[1fr_20rem]`; ცხრილი `min-w-[52rem]` საკუთარ `overflow-x-auto`-ში.
- z-index: header 40 · drawer 50 · modal 60 · toast 70 · skip-link 80.

## A.5 ფორმები (admin)
- Radii: `rounded-control` 0.625rem (ღილაკი, input, ფილა) · `rounded-card` 0.875rem (ბარათი, toast, მოდალი) · `rounded-pill` (ბეჯი). Admin-ში დამატებით პირდაპირ Tailwind: `rounded-xl` (ცხრილი/სექცია), `rounded-lg` (nav, ბანერი, ძებნა).
- ჩრდილები: `shadow-sm` (solid ღილაკი); `card` `0 1px 2px / 0 1px 3px` (rgb 18 21 29 / .04–.06); `card-hover` `0 10px 24px -6px /.14`; `popover` `0 12px 32px -8px /.22` (toast, მოდალი); `header` `0 1px 0 0 /.06`; `glow` (hover ბარათი, primary-400/600) — dark-ზე ჩრდილის ნაცვლად. Admin ბარათებს ჩრდილი არ აქვს, მხოლოდ `border border-ink-200`.
- ანიმაცია: fade-in 180ms, slide-up 220ms, sheet-up/slide-in 260ms; `prefers-reduced-motion` ყველაფერს ასუსტებს ~0.

## A.6 კომპონენტები და მდგომარეობები (admin; shared კომპონენტებისთვის ეს admin-მნიშვნელობაა)
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

**Admin statusები** (`StatusBadge.jsx`, `statuses.jsx`): `rounded-full px-2 py-0.5 text-xs font-medium`; შეკვეთა: მიღებული ink-100/700 · დადასტურებული primary-50/700 · მუშავდება warning-50/600 · გაგზავნილი accent-50/800 · მიწოდებული success-50/700 · გაუქმებული danger-50/700.

**ბარათი:** admin სექცია `rounded-xl border border-ink-200 bg-white p-4`.

**ცხრილი (admin `DataTable`):** კონტეინერი `rounded-xl border border-ink-200 bg-white`; th იხ. §A.3, `px-3 py-2.5`; სტრიქონი `border-b border-ink-100 hover:bg-ink-50`; loading = 6 `Skeleton h-10`; empty = გადმოცემული `EmptyState`; `caption` sr-only. Pagination: `h-9 rounded-lg border-ink-300`, disabled `opacity-40`.

**დიალოგი:** `Modal` — `role="dialog" aria-modal`, ESC, focus trap, ფოკუსის დაბრუნება; ფონი `bg-scrim/50`; პანელი `bg-surface shadow-popover rounded-card`, სათაური `border-b px-5 py-4 text-base font-semibold`, ზომები sm…2xl (default lg). `ConfirmDialog` (admin): ტექსტი `p-5 text-sm text-ink-600`, ღილაკები მარჯვნივ `gap-2`: outline sm "გაუქმება" + `variant` (default danger) sm; confirm `loading` ხანგრძლივობისას, დახურვა დაბლოკილია.

**Toast** (`Toast.jsx`; admin-ში toast-ის გამოყენება **ვერ დადგინდა** — admin-ი inline ბანერებს იყენებს): ქვემოთ, `max-w-sm rounded-card border bg-surface shadow-popover px-4 py-3`, საზღვარი `success/danger/primary-500/30`, იკონი 20px (`CheckCircle2` success-600 · `AlertCircle` danger-fg · `Info` primary-700), ტექსტი `text-sm font-medium`, ქმედება `text-primary-700 font-semibold`, ჯგუფი `aria-live="polite"`.

**ბანერები (admin, inline):** შეცდომა — `<p role="alert" class="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">` (OrderDetail, ProductForm); გაფრთხილება — `rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-600` + `AlertTriangle h-4 w-4` (ProductForm:351), საზღვრის გარეშე.

**ნავიგაცია (admin):** Admin sidebar (`md:`+): `w-56 bg-white border-r`, ელემენტი `rounded-lg px-3 py-2 text-sm`, აქტიური `bg-accent-50 text-accent-800 font-medium`, hover `bg-ink-100`; top bar h-14, "მაღაზიაში" (ბორდერიანი ბმული) და "ანგარიშიდან გასვლა" (hover danger-50/700).

## A.7 გვერდის მდგომარეობები (shared; admin-მნიშვნელობა)
- **Loading:** `Skeleton` (`bg-ink-200/70`, shimmer 1.6s) — spinner-ის ნაცვლად; ბარათის სკელეტონი ბარათის იდენტური გეომეტრიით; admin დეტალი `Skeleton h-96 w-full`; სათაურში "იტვირთება…".
- **Empty:** `EmptyState` — `rounded-card border border-dashed border-ink-300 bg-surface px-6 py-14 text-center`, 64px წრე `bg-ink-100` + 28px `text-ink-500` იკონი, სათაური `text-lg font-semibold`, აღწერა `text-sm text-ink-600`, მოქმედების `Button` (თუ არსებობს).
- **Error:** `ErrorState` — `role="alert"`, `rounded-card border-danger-100 bg-danger-50 py-12 text-center`, `AlertTriangle` danger-fg 56px წრეში `bg-danger-100`, სათაური ink-900, ტექსტი ink-700, `outline` "ხელახლა" ღილაკი `RotateCcw`-ით.

## A.8 სურათები და იკონები (admin)
- იკონები: **lucide-react** (MIT), 16px (`h-4 w-4`) ღილაკებსა და ველებში, 20px toast/ნავიგაცია, `aria-hidden="true"`; იკონ-ღილაკს `aria-label` აქვს. სხვა ნაკრები არ არის.
- პროდუქტის ფოტო `ProductImage` — `aspect-square rounded-control` ღია ფილაზე (`media` #eef0f4, ყველა თემაში), ბარათის კიდიდან `p-2`-ით; hover `scale-1.04`. ფოტოს არქონისას placeholder-ის ზუსტი წესი `ProductImage.jsx`-ში (ამ დოკუმენტისთვის არ გადამიმოწმებია — ვერ დადგინდა).
- ლოგო: Admin-ში `Store` იკონი accent-600-ით + "VoltBox" + ბეჯი "ადმინი" (`bg-ink-100 text-ink-600 text-[11px]`).

## A.9 Admin: destructive actions and trash (Stage 2 — შეკვეთების სანაგვე)
მხოლოდ არსებული ტოკენები და კომპონენტები; ახალი ფერი/კომპონენტი არ შემოდის. ტექსტი ქართულია, პირდაპირ JSX-ში (admin-ის წესი). ყველა admin ფერი light-ია.
1. **"წაშლა" (OrderDetail):** `Button variant="danger" size="sm"` + `Trash2 h-4 w-4` (როგორც ProductList-ში), იმავე ღილაკების რიგში, სადაც `allowedTransitions` (`mb-4 flex flex-wrap gap-2`), სტატუსის ღილაკების მარჯვნივ/ბოლოს. დადასტურება: `ConfirmDialog` როგორც `ProductList` (`title` + `description` რა მოხდება და როდის წაიშლება სამუდამოდ, `confirmLabel="წაშლა"` — ღილაკის სიტყვა = დიალოგის ღილაკის სიტყვა, `variant="danger"`). შეცდომა — OrderDetail-ის `actionError` ბანერი (`role="alert"`, danger-50/700, 5.92:1).
2. **გაფრთხილების ბანერი სანაგვეში მყოფ შეკვეთაზე:** ProductForm:351-ის გაფრთხილების ბანერის პატერნი — `rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-600` (4.74:1) + `AlertTriangle h-4 w-4`; ტექსტი: წაშლის თარიღი `dateOnly()`-ით (`admin/format.js`, როგორც ProductList-ის "დამატებული" სვეტი). ადგილი: `<header>`-სა და სტატუსის ღილაკებს შორის. რადგან ტექსტი შეიცავს სტატუსს/თარიღს და არა სიახლეს, `role` არ სჭირდება (ProductForm-ის გაფრთხილებასაც არ აქვს). ამავე ბანერში "აღდგენა" `outline sm` ღილაკი (აღდგენის ქმედება გვერდზეც უნდა იყოს).
3. **"სანაგვე" გადამრთველი სიაზე (OrderList):** ProductList-ის `lowStock` checkbox-ის პატერნი ზუსტად: `<label class="mb-3 flex w-fit items-center gap-2 text-sm text-ink-700">` + checkbox `h-4 w-4 rounded border-ink-300 text-accent-600 focus:ring-accent-600/30`; მდგომარეობა URL-ის query-ში `setParam('trash', event.target.checked)`. ფილტრების პანელის ქვემოთ, ცხრილის ზემოთ. ჩართულზე `EmptyState`: "სანაგვე ცარიელია" (იგივე `EmptyState`, ღილაკის გარეშე).
4. **სტრიქონის ღილაკები (სანაგვის რეჟიმში):** ახალი "ქმედებების" სვეტი — `align: 'right'`, `render: <span className="flex justify-end gap-1">` (ProductList-ის `actions` სვეტი). "აღდგენა" — `Button variant="outline" size="xs"` (admin-ის მეორადი = ConfirmDialog-ის "გაუქმება"; `variant="secondary"` არ გამოიყენო — ის მუქი ინკის solid ღილაკია). "სამუდამოდ წაშლა" — `Button variant="danger" size="xs"`, ხსნის `ConfirmDialog`-ს `confirmLabel="სამუდამოდ წაშლა"` (ProductList-ის ზუსტი სიტყვა), `variant="danger"`, აღწერაში "ქმედება შეუქცევადია". `aria-label` რიგის ნომრით (`${order.orderNumber} — აღდგენა`), როგორც ProductList-ში. in-flight: `loading` prop. რიგის სტატუსი — `OrderStatusBadge`; სანაგვის მარკერისთვის (თუ საჭიროა) neutral pill `bg-ink-100 text-ink-700` (7.29:1) — **(დამატებულია)**, ახალი ფერის გარეშე.
5. კონტრასტი: white on danger-600 4.83:1, on danger-700 (hover) 6.47:1; outline ink-800/white 11.38:1 — AA სრულდება. წაშლისას აკრძალული: ახალი hex, `dark:`, `window.confirm`.
ვერ დადგინდა: წარმატების შეტყობინება აღდგენის/წაშლის შემდეგ (admin-ში toast-ის გამოყენება არ ჩანს) — უმარტივესი: სტრიქონი უბრალოდ ქრება და სია ახლდება (`reloadToken`, როგორც ProductList-ში).
