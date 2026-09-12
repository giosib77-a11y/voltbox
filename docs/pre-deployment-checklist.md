# VoltBox — Pre-Deployment Checklist

Deployment-მდე მისატანი სამუშაოს ერთადერთი წყარო. სექციები რიგზე მიდის;
შემდეგზე გადასვლა მხოლოდ მიმდინარეს დახურვის შემდეგ.

**წესი:** პუნქტი ✅-ით მხოლოდ მაშინ აღინიშნება, როცა **გაშვებით** გადამოწმდა.
დოკუმენტაცია, README, ROADMAP და წინა მტკიცებები საკმარისი არაა.

```
✅ გადამოწმებული    ⚠️ გასაუმჯობესებელი    ❌ გატეხილი / არ არსებობს
🔴 კრიტიკული        🟡 საშუალო             🟢 მცირე
⬜ ჯერ არ შემოწმებულა
```

---

## 0. საბოლოო Development Audit — ✅ დახურულია (2026-09-12)

- [x] პროექტის სტრუქტურის სრული შემოწმება
- [x] Frontend build წარმატებით სრულდება — `vite build` **ორივე** რეჟიმში (mock, http)
- [x] Backend startup წარმატებით სრულდება — ცოცხალი `/api/v1/health` → 200
- [x] ყველა test გადის — pytest **450**, vitest **77**
- [x] lint გადის — `ruff check`, `ruff format --check`, `eslint` (0 შეცდომა)
- [x] type checking გადის — `mypy` strict, 73 მოდული
- [x] არ არის TODO/FIXME, რომელიც production-ს უშლის ხელს
- [x] არ არის development-only mock, რომელიც production-ში გაჟონავს
- [x] არ არის hardcoded URL, secret ან credential
- [x] არ არის console error / uncaught error კრიტიკულ flow-ებში

### რა გასწორდა

| # | პრობლემა | გასწორება |
|---|---|---|
| 🔴 | Supabase `0004`-ზე იდო, კოდი `0005`-ზე. `refresh_tokens.family_id` არ არსებობდა — **login და register 500-ს აბრუნებდა** | მიგრაცია გაშვებულია SQL Editor-იდან; `alembic check` სუფთაა |
| 🟡 | `get_storage()` ჩუმად `InMemoryStorage`-ზე ეშვებოდა **production-შიც** | production/staging-ში `RuntimeError` — `backend/app/services/storage.py` |
| 🟢 | `frontend/.env` git-ში იდო; deploy-ზე `/api/v1`-ს ჩუმად თავს მოახვევდა ბილდს | git-იდან მოხსნილია, დისკზე დარჩა; README-ები გასწორდა |

### გადამოწმების მტკიცებულება

```
alembic check           → No new upgrade operations detected
public.refresh_tokens   → family_id NOT NULL, 6/6 შევსებული
auth.refresh_tokens     → ხელუხლებელი (GoTrue-ს ცხრილი)
register → 201 · login → 200 · refresh → 200 · logout → 200 · refresh → 401
token families          → როტაცია ოჯახს ინარჩუნებს
```

`get_storage()`-ის 6 ახალი ტესტი დამტკიცდა ბაგის დროებით დაბრუნებით:
დაცვის მოხსნაზე 3 ჩავარდა, დაბრუნებაზე გაიარა.

### გადატანილი სხვა სექციებში

| რა | სად |
|---|---|
| ErrorBoundary-ს TODO — მონიტორინგის სერვისი | §20 Logging / Monitoring |
| `REDIS_URL` ცარიელია (კონტეინერი გაშვებულია) | §4 Security / rate limiting |
| `CORS_ORIGINS` default `localhost`, production-ის დაცვის გარეშე | §4 Security |

---

## 1. Database / Supabase — ✅ დახურულია (2026-09-12)

- [x] Production database სწორად შექმნილია — PostgreSQL 17.6, eu-central-1
- [x] ყველა migration სწორად გაშვებულია — Supabase `0006`, `alembic check` სუფთა
- [x] database schema სრულად განახლებულია — `alembic check` სუფთა
- [x] ყველა foreign key შემოწმებულია — 15, ყველა მოდელს ემთხვევა
- [x] ყველა საჭირო unique constraint შემოწმებულია — 9
- [x] ყველა საჭირო index შემოწმებულია — 45 (`ix_order_items_product_id` დაემატა)
- [x] Product მონაცემები სწორად ინახება — `Numeric(12,2)`, 4 CHECK
- [x] Category მონაცემები სწორად ინახება — self-FK SET NULL, unique slug
- [x] User მონაცემები სწორად ინახება — `citext` email, unique
- [x] Order მონაცემები სწორად ინახება — 3 CHECK, unique order_number + idempotency_key
- [ ] Cart მონაცემები სწორად ინახება — **ბაზაში cart არ არსებობს** (იხ. ქვემოთ) → §8
- [x] Stock მონაცემები სწორად ცვლილდება — `inventory_movements` ledger, 3 CHECK
- [x] concurrent order / stock შემცირება ტესტირებულია — 8 ტესტი რეალურ Postgres-ზე
- [x] transaction boundaries შემოწმებულია — თითო მოთხოვნა ერთი სესია, შეცდომაზე rollback
- [x] connection/pool configuration შემოწმებულია — გასწორდა, იხ. ქვემოთ
- [ ] production backup ჩართულია — 🔴 **Free Plan-ს backup არ აქვს.** გადაწყვეტილება გაშვებამდე → §21
- [x] backup restore პროცედურაც ტესტირებულია — `docs/backup-restore.md`, 0 შეუსაბამობა

### რა გასწორდა

| # | პრობლემა | გასწორება |
|---|---|---|
| 🟡 | `order_items.product_id` ინდექსის გარეშე. პროდუქტის წაშლა ცხრილს **ორჯერ** სკანირებდა (count + RESTRICT). გაზომილი: 13.6 ms → 1.25 ms 200k მწკრივზე | მიგრაცია `0006` |
| 🟡 | `workers × (pool+overflow)` = 30/30 ბიუჯეტიდან. `WEB_CONCURRENCY=4` → 60 კავშირი, ლიმიტს გადააჭარბებდა და დატვირთვაზე შემთხვევით 500-ებს მოგვცემდა | გაშვების შემოწმება `gunicorn.conf.py`-ში |
| 🟡 | `pg_dump`-ის შედეგი **არ აღდგებოდა**: ვერცერთი `CREATE EXTENSION` (საჭიროა citext, pg_trgm, unaccent) + PG17→PG16 შეუთავსებლობა | `docs/backup-restore.md` — გაშვებული და გადამოწმებული |

### გადამოწმების მტკიცებულება

```
Supabase 0006-ის შემდეგ:
  Seq Scan  →  Index Only Scan using ix_order_items_product_id
  alembic check: No new upgrade operations detected

restore სუფთა PG17-ში, შედარება ცოცხალთან:
  tables 13/13 · columns 129/129 · indexes 44/44
  fkeys 15/15 · checks 12/12 · uniques 9/9 · alembic 0005/0005
  MISMATCHES: 0
```

მიგრაცია `0006` ლოკალურად ორივე მიმართულებით გაშვებულია (upgrade + downgrade),
`alembic check` შემდეგ სუფთაა. კავშირების დაცვის 6 ტესტი დამტკიცდა ბაგის
დროებით დაბრუნებით.

### გადატანილი სხვა სექციებში

| რა | სად |
|---|---|
| **Cart ბაზაში არ ინახება** — მხოლოდ ბრაუზერშია. მოწყობილობებს შორის არ სინქრონდება | §8 Cart |
| ლოკალური Postgres **16**, production **17.6** — production-ის backup ლოკალურად ვერ აღდგება; პროცედურა `docs/backup-restore.md` §3-შია | §19 Testing / CI |
| 🔴 **ავტომატური backup არ არსებობს** — Free Plan-ს არც scheduled, არც PITR. ვარიანტები `docs/backup-restore.md`-ში | §21 Backup / Recovery |

---

## 2. Environment Variables / Secrets — ✅ დახურულია (2026-09-12)

- [x] Development და Production environment-ები გამიჯნულია — გასწორდა, იხ. ქვემოთ
- [x] ყველა საჭირო env variable ჩამოწერილია — 32 პარამეტრიდან 27 `.env.example`-ში
- [x] production secrets GitHub-ში არ არის — **მთელი ისტორია** შემოწმებულია
- [x] `.env` ფაილები repository-ში არ არის — `backend/.env` და `frontend/.env` (§0)
- [x] API keys დაცულია — `SUPABASE_SERVICE_ROLE_KEY` მხოლოდ backend-ზე
- [x] JWT/session secrets დაცულია — ისტორიაში ნამდვილი მნიშვნელობა არასოდეს ყოფილა
- [x] database credentials დაცულია — ისტორიაში მხოლოდ `voltbox:voltbox` (ლოკალური/CI)
- [x] frontend-ში secret მნიშვნელობები არ ხვდება — ბანდლი შემოწმებულია
- [x] production configuration values განახლებულია — გასწორდა, იხ. ქვემოთ

### რა გასწორდა

| # | პრობლემა | გასწორება |
|---|---|---|
| 🔴 | `APP_ENV` დაყენების დავიწყება **ხუთივე დაცვას ერთდროულად ხსნიდა**: `/docs` საჯარო, cookie `Secure`-ის გარეშე, storage მეხსიერებაში, proxy-ისა და pool-ის შემოწმებები გამოტოვებული — და საიტი მაინც მუშაობდა | `gunicorn.conf.py` ჩერდება; ლოკალურ გაშვებას `ALLOW_NON_PRODUCTION_SERVER=1` სჭირდება |
| 🟡 | `/docs` და `/openapi.json` **staging-ზე საჯარო იყო** — `is_production` მხოლოდ `production`-ს ცნობდა | ახალი `is_deployed` — staging-იც დეპლოია |
| 🟡 | 12 პარამეტრი მხოლოდ კოდში არსებობდა, მათ შორის `TRUSTED_HOSTS=*`, `DB_SSL_MODE`, `DB_ECHO` | `.env.example` შევსებულია, თითოეულთან რისკის ახსნით |

### გადამოწმების მტკიცებულება

```
git log --all -p  →  ვერცერთი ნამდვილი პაროლი, გასაღები ან JWT_SECRET
CI workflows      →  secrets.* საერთოდ არ გამოიყენება
frontend dist/    →  არც VITE_ სახელი, არც Supabase, არც გასაღები
                     API base = "/api/v1" — ბრაუზერი Supabase-ს არ ხედავს

APP_ENV=development  /docs: True    ← ლოკალური
APP_ENV=staging      /docs: False
APP_ENV=production   /docs: False

gunicorn, APP_ENV დაუყენებელი  →  REFUSED
gunicorn, APP_ENV=production   →  STARTED
```

12 ახალი ტესტი დამტკიცდა ორივე დაცვის დროებით მოხსნით — 6 ჩავარდა, დაბრუნებაზე გაიარა.

### გადატანილი სხვა სექციებში

| რა | სად |
|---|---|
| `TRUSTED_HOSTS=*` — Host-ის შემოწმება გამორთულია (ახლა დოკუმენტირებულია, მაგრამ დეპლოიზე უნდა დაყენდეს) | §4 Security |
| `DB_SSL_MODE=require` — შიფრავს, სერვერს არ ამოწმებს. `verify-full` ითხოვს CA-ს ჩამოტვირთვას | §4 Security |
| `CORS_ORIGINS` დეპლოიზე რეალური დომენით | §24 Domain / Deployment |

---

## 3. Authentication — ✅ დახურულია (2026-09-12)

### Register
- [x] ახალი user-ის რეგისტრაცია მუშაობს — ცოცხალ Supabase-ზე 201
- [x] email validation მუშაობს — `EmailStr`, reserved დომენებსაც აგდებს
- [x] duplicate email სწორად მუშავდება — 409, რეგისტრზე დამოუკიდებლად (`citext`)
- [x] password validation მუშაობს — მინ. 8, 17 გავრცელებული პაროლი აკრძალული, მაქს. 128
- [x] password უსაფრთხოდ hash-დება — **Argon2id** (OWASP-ის რეკომენდაცია)
- [x] არასწორ input-ზე error სწორად ბრუნდება — `VALIDATION_ERROR` კონვერტით

### Login
- [x] სწორი login მუშაობს
- [x] არასწორი password სწორად ბრუნდება — არარსებულ user-ისგან **განურჩეველი**
- [x] არარსებული user სწორად მუშავდება — dummy hash დროს ათანაბრებს
- [x] access token/session flow მუშაობს — JWT, `type=access`, `algorithms=[...]` ცხადი სიით
- [x] refresh token flow მუშაობს
- [x] refresh token უსაფრთხოდ ინახება — httpOnly, `Path=/api/v1/auth`, ბაზაში მხოლოდ SHA-256
- [x] logout მუშაობს — ბაზაშიც უქმდება, არა მხოლოდ ბრაუზერში
- [x] expired session სწორად მუშავდება — **ტესტები დაემატა**
- [x] refresh token rotation/invalidation მუშაობს — ერთი conditional UPDATE, race-ის გარეშე

### Authorization
- [x] ჩვეულებრივი user ვერ შედის admin API-ზე — **33 ოპერაცია × 3 შემოწმება**
- [x] ჩვეულებრივი user ვერ ასრულებს admin action-ს — იგივე
- [x] user-ს სხვისი მონაცემების ნახვა არ შეუძლია — მისამართი 404-ს აბრუნებს
- [x] user-ს სხვისი order-ის ნახვა არ შეუძლია — **ტესტი დაემატა**
- [x] backend authorization გადამოწმებულია — ცოცხლადაც
- [x] frontend route protection გადამოწმებულია — `RequireAuth` + `RequireAdmin`

### რა იყო უკვე ძლიერი

| | |
|---|---|
| **როლი JWT-დან არასოდეს იკითხება** | `require_admin` ყოველ მოთხოვნაზე ბაზას კითხულობს, ანუ დაბლოკვა და როლის ჩამორთმევა **მყისიერად** მოქმედებს, არა 30 წუთში |
| **დაცვა router-ის დონეზეა** | ახალი admin endpoint იცავს თავს ჩართვისთანავე; დავიწყებული დეკორატორი შეუძლებელია |
| **ტესტი ცოცხალ OpenAPI-ს კითხულობს** | ხელით სიას არ ეყრდნობა — ახალი როუტი ავტომატურად იფარება |
| **404 და არა 403** | არც შეკვეთის, არც მისამართის არსებობა არ ჟონავს |

### რა დაემატა

| # | ხარვეზი | ტესტი |
|---|---|---|
| 🟡 | `GET /orders/{order_number}` ჯვარედინი წვდომა არსად არ იტესტებოდა (სია — კი) | 2 ტესტი |
| 🟡 | **ვადაგასული ტოკენი არსად არ იტესტებოდა** — `expires_at`-ის პირობის წაშლა შეუმჩნეველი დარჩებოდა | 4 ტესტი |

ექვსივე დამტკიცდა ბაგის დროებით შეტანით: მფლობელობის შემოწმების დასუსტებაზე
2 ჩავარდა, `expires_at`-ის წაშლაზე — 2.

### გადამოწმების მტკიცებულება

```
admin routes: 33 ოპერაცია
  ანონიმური           → 401 INVALID_TOKEN
  ჩვეულებრივი user    → 403 ADMIN_REQUIRED
  დეაქტივირებული admin → 401

ცოცხალი სერვერი:
  /admin/{me,products,dashboard,customers,orders}  ანონიმური → 401
  სხვისი გასაღებით ხელმოწერილი JWT                → 401
  /orders /addresses /auth/me  ანონიმური           → 401
```

### გადატანილი სხვა სექციებში

| რა | სად |
|---|---|
| access token-ის გაუქმება არ არსებობს — მოპარული 30 წუთი მოქმედებს (`jti` მზადაა) | §4 Security |
| ანგარიშზე მიბმული lockout არ არის — rate limit მხოლოდ IP-ზეა (ბოტნეტი გვერდს უვლის) | §4 Security |
| email-ის დადასტურება არ არსებობს — ფოსტის გაგზავნა საერთოდ არ გვაქვს | §22/§23 |

---

## 4. Security Audit — 🟡 თითქმის დახურული (2026-09-12)

- [ ] HTTPS გამოყენებისთვის მზადაა — HSTS იგზავნება დეპლოიზე; TLS თვითონ hosting-ს ეკუთვნის → §24
- [ ] CORS production configuration სწორია — კოდი სწორია, **მნიშვნელობა დეპლოიზე** → §24
- [x] rate limiting ჩართულია — 5/წთ ავტორიზაციაზე, 10/წთ lookup-ზე, 60/წთ ნაგულისხმევი; გასწორდა
- [x] forwarded IP / proxy configuration სწორია — `X-Forwarded-For` მხოლოდ დასახელებულ proxy-ს სჯერა
- [x] brute-force protection შემოწმებულია — იხ. შეზღუდვა ქვემოთ
- [x] input validation ყველა endpoint-ზე მუშაობს — `extra="forbid"` ყველა მოთხოვნაზე
- [x] SQL injection-ის რისკი შემოწმებულია — **სტრიქონით აწყობილი SQL არსად არაა**
- [x] XSS-ის რისკი შემოწმებულია — `dangerouslySetInnerHTML`/`innerHTML`/`eval` საერთოდ არ არსებობს
- [x] CSRF-ის საჭიროება/დაცვა შემოწმებულია — Bearer + `SameSite=strict` ერთადერთ cookie-ზე
- [x] sensitive data response-ში არ ხვდება — OpenAPI-ს სქემა შემოწმებულია
- [x] stack trace production response-ში არ ხვდება — §0
- [x] debug mode გამორთულია — `debug=True` არსად; `DB_ECHO` დოკუმენტირებულია
- [x] admin endpoints დაცულია — §3, 33 ოპერაცია × 3
- [x] security headers განახლებულია — **დაემატა**
- [x] dependency security audit შესრულებულია — `docs/dependency-audit.md`
- [x] მოძველებული / vulnerable dependency-ები შეფასებულია — 8-დან 7 dev-ია
- [ ] secrets rotation — ჯერ არ დამდგარა (გასაღებები არ გაჟონილა) → გაშვებამდე

### რა გასწორდა

| # | პრობლემა | გასწორება |
|---|---|---|
| 🟡 | **ვერცერთი security header არ იგზავნებოდა** | `SecurityHeadersMiddleware` — nosniff, frame-ancestors, no-referrer, CSP; HSTS მხოლოდ დეპლოიზე |
| 🟡 | `REDIS_URL`-ის გარეშე ორი worker **ყოველ ლიმიტს აორმაგებდა** — მათ შორის შესვლისას. მხოლოდ გაფრთხილება იყო | `gunicorn.conf.py` ჩერდება; ერთი worker ხელუხლებელია |
| 🟢 | react-router-ის open redirect advisory შეფასებული არ იყო | 10 payload-იანი ტესტი + `docs/dependency-audit.md` |

### რა იყო უკვე ძლიერი

| | |
|---|---|
| **SQL injection** | სტრიქონით აწყობილი SQL **არსად არაა** — ყველა `text()` სტატიკური ლიტერალია |
| **XSS** | `dangerouslySetInnerHTML`, `innerHTML`, `eval` — არცერთი არ არსებობს |
| **ფასის გაყალბება** | `extra="forbid"` — კლიენტის გამოგზავნილი `price` 400-ს იწვევს, არა ჩუმ იგნორს |
| **CSRF** | ყველაფერი Bearer-ზეა; ერთადერთი cookie `SameSite=strict` — ჯვარედინი მოთხოვნა მას საერთოდ არ ატარებს |
| **ლოგები** | სხეული არასოდეს იწერება; `/auth`-ზე query-ც არა |

### გადამოწმების მტკიცებულება

```
ცოცხალი პროცესი:
  x-content-type-options: nosniff
  x-frame-options: DENY
  referrer-policy: no-referrer
  content-security-policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'
  401-ზეც იგზავნება

Set-Cookie: voltbox_refresh=…; HttpOnly; Max-Age=2592000; Path=/api/v1/auth; SameSite=strict

pip-audit  →  No known vulnerabilities found
npm audit  →  8, აქედან 7 dev-only; მე-8 ნეიტრალიზებულია getSafeRedirect-ით
```

21 ახალი ტესტი დამტკიცდა დაცვების დროებითი მოხსნით — 12 ჩავარდა.

### რაც განზრახ არ გაკეთდა

| რა | რატომ |
|---|---|
| `TRUSTED_HOSTS`-ზე დაცვა | **არცერთი კოდი არ იყენებს `Host`-ს** — არაფრისგან დაცვა იქნებოდა. მნიშვნელობა დოკუმენტირებულია და დეპლოიზე უნდა დაყენდეს |
| access token-ის გაუქმება | მოპარული ტოკენი 30 წუთს მუშაობს. `jti` უკვე იწერება, ანუ deny-list მოგვიანებით დაემატება → ROADMAP §20 |
| ანგარიშზე lockout | rate limit მხოლოდ IP-ზეა, ბოტნეტი გვერდს უვლის. lockout კი საკუთარ DoS-ს ქმნის (მოწინააღმდეგეს შეუძლია ანგარიში განგებ ჩაკეტოს) |
| `vite`/`vitest` major | dev-only ხარვეზები; ცალკე სამუშაოა → ROADMAP §18 |

---

## 5. Product Management — ✅ დახურულია (2026-09-12)

- [x] პროდუქტის შექმნა მუშაობს — end-to-end გაშვებული
- [x] პროდუქტის რედაქტირება მუშაობს — სახელი, ფასი, კატეგორია, აღწერა
- [x] პროდუქტის წაშლა მუშაობს — 204, შეკვეთაში მყოფი უარყოფილია
- [x] აქტიური/არააქტიური მდგომარეობა მუშაობს — არააქტიური მაღაზიაში 404
- [x] category სწორად მუშაობს — გადატანა მუშაობს, არარსებული უარყოფილია
- [x] brand სწორად მუშაობს — სახელი მაღაზიაში სწორად ჩანს
- [x] price სწორად ინახება — `2499.99` ზუსტად, float-ად არასოდეს იქცევა
- [x] discount სწორად ითვლება — **გასწორდა**, იხ. ქვემოთ
- [x] stock სწორად ინახება — ledger-ით, პირდაპირ ჩაწერა შეუძლებელია
- [x] out-of-stock მდგომარეობა მუშაობს — პროდუქტი ჩანს, `inStock: false`
- [x] product image upload/display მუშაობს — პირველი primary ხდება, SVG უარყოფილი
- [x] description სწორად ინახება
- [x] SKU სწორად მუშაობს — დუბლიკატი 409
- [x] invalid product data უარყოფილია — 6 შემთხვევა, ყველა 400
- [x] frontend display backend-ს შეესაბამება — კონტრაქტი ორივე მიმართულებით შემოწმებული

### რა გასწორდა

| # | პრობლემა | გასწორება |
|---|---|---|
| 🟡 | **ტესტი production-ის bucket-ში წერდა.** `get_storage()` `SUPABASE_*`-ს `APP_ENV`-ის მიუხედავად კითხულობდა — ანუ ლოკალურ ბაზაზე გაშვებული ტესტი ცოცხალ საცავში ტოვებდა ფაილს. **bucket-ში 150 ობოლი ფაილია** | `app_env == "test"` → ყოველთვის `InMemoryStorage` |
| 🟢 | **ფასდაკლება backend-სა და frontend-ში სხვაობდა** ზუსტად ნახევრიან პროცენტებზე. 7347 წყვილიდან 38 | თეთრებში, მთელი რიცხვებით |

### გადამოწმების მტკიცებულება

```
end-to-end სუფთა ლოკალურ ბაზაზე:  39/39 გავიდა
  create → 201 · slug · price 2499.99 ზუსტად · draft-ად იწყება
  6 არასწორი შემთხვევა → 400 · დუბლიკატი SKU → 409
  edit → 200 · image → 201, primary · SVG → 400
  activate → მაღაზიაში 200 · deactivate → 404
  stock 0 → inStock false, პროდუქტი ისევ ჩანს
  delete → 204 → 404

ფასდაკლების შედარება backend ↔ frontend:
  ფართო ნაკრები  6783 წყვილი → 0 განსხვავება
  ზუსტად .5-ზე    564 წყვილი → 38 განსხვავება (გასწორდა → 0)

კონტრაქტი:
  ProductForm აგზავნის, backend არ იღებს → არცერთი
  ProductForm კითხულობს, backend არ აგზავნის → არცერთი
```

### გადატანილი სხვა სექციებში

არაფერი — bucket-ის 150 ობოლი ფაილი **წაშლილია** (2026-09-12). წაშლამდე
გადამოწმდა, რომ `product_images = 0` და `order_items = 0`, ანუ ვერცერთზე
ვერაფერი მიუთითებდა. შემდეგ: 0 ფაილი, bucket უცვლელი და მუშა (ატვირთვა →
საჯარო GET 200 → წაშლა).

---

## 6–25 — ⬜ ჯერ არ დაწყებულა

`6. Product Page / Catalog` · `7. Search / Filtering` · `8. Cart` · `9. Checkout` ·
`10. Orders` · `11. Admin Panel` · `12. Order Status / Business Flow` ·
`13. Error Handling` · `14. Performance` · `15. SEO` · `16. Accessibility` ·
`17. Responsive / Browser` · `18. Full E2E` · `19. Testing / CI` ·
`20. Logging / Monitoring` · `21. Backup / Recovery` · `22. Payment` ·
`23. Analytics` · `24. Domain / Deployment` · `25. Final Launch`

პუნქტები სრული სახით — `voltbox_pre_deployment_checklist.md` (საწყისი დოკუმენტი).

---

## Release Gate

deployment-მდე ყველა უნდა იყოს ✅:

Authentication · Authorization · Database · Products · Cart · Checkout ·
Orders · Stock · Admin · Security · Error handling · Tests · Production build ·
Backup · Monitoring · HTTPS · Domain · Final E2E

გაშვების შემდეგ შეიძლება: Wishlist · Reviews · Product comparison ·
Recently viewed · Promo codes · Advanced analytics · Recommendations
