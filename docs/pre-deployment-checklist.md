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

## 4. Security Audit — ✅ დახურულია კოდის მხრივ (2026-09-12)

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
| ~~`TRUSTED_HOSTS`-ზე დაცვა~~ | **გაკეთდა.** `*`-ით ან ცარიელით gunicorn ჩერდება |
| ~~access token-ის გაუქმება~~ | **გაკეთდა.** `users.token_version` ტოკენში `tv`-დ მიდის; პაროლის შეცვლა მოპარულ ტოკენს მყისვე კლავს |
| ~~ანგარიშზე lockout~~ | **გაკეთდა.** 10 შეცდომა → 15 წუთი, ანგარიშზე მიბმული. DoS-ის რისკი შეგნებულად მიღებულია და შეზღუდულია |
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

## 6. Product Page / Catalog — ✅ დახურულია (2026-09-12)

- [x] კატეგორიები მუშაობს — 6 კატეგორია, ყველას აქვს slug და name
- [x] პროდუქტის listing მუშაობს — pagination-ის კონვერტი სრული
- [x] პროდუქტის დეტალური გვერდი მუშაობს — 11 ველი ყველა ადგილზეა
- [x] **ყველა პროდუქტი სწორად ეტვირთება** — 59/59 მიწვდომადი, 0 დუბლიკატი
- [x] პროდუქტის სურათი ეტვირთება — listing-ში 12/12
- [x] ფასი სწორად — ბაზას ზუსტად ემთხვევა
- [x] ფასდაკლება სწორად — §5-ში გასწორდა, აქ გადამოწმდა
- [x] stock status სწორად — 0 მარაგზე `inStock: false`, პროდუქტი ისევ ჩანს
- [x] quantity selection მუშაობს — მარაგით შეზღუდული, ხელით აკრეფაც ილექება
- [x] add to cart მუშაობს — მარაგის გარეშე ღილაკი გამორთულია
- [x] unavailable product სწორად ჩანს — არქივი და არააქტიური 404
- [x] loading state არსებობს — Category, ProductDetails, Home, SearchResults
- [x] empty state არსებობს — **ტესტი დაემატა**
- [x] API error state არსებობს — `ErrorState` + retry ოთხივე გვერდზე
- [x] broken image დამუშავებულია — **ტესტი დაემატა**

### გასწორება არ დასჭირვებია

ეს სექცია უკვე სწორი იყო. 45 შემოწმებიდან 44 გაიარა, ერთი კი **ჩემი მოლოდინი
იყო არასწორი**: მაღაზია უცნობ `sort`-ს ჩუმად ნაგულისხმევზე აბრუნებს (ძველი
ბმული 400-ს არ უნდა იღებდეს), ადმინი კი უარყოფს. ორივე განზრახაა და
`SORTABLE.get(sort, DEFAULT)` თეთრი სიის ძებნაა — ინტერპოლაცია არსად.

### რა დაემატა

| # | ხარვეზი | ტესტი |
|---|---|---|
| 🟢 | `ProductImage`-ის fallback არსად არ იტესტებოდა. კრიტიკული ნაწილი — როცა **placeholder-იც** ჩავარდება: skeleton state-ზეა და დასრულებული გვერდი სამუდამოდ ციმციმებდა | 6 ტესტი |
| 🟢 | `ProductCarousel`-ის ცარიელი ქცევა არ იტესტებოდა. **ეს შენი ახლანდელი მდგომარეობაა** — 0 პროდუქტით სათაურიანი ცარიელი რიგი გატეხილად წაიკითხებოდა | 7 ტესტი |

### გადამოწმების მტკიცებულება

```
catalog end-to-end (61 პროდუქტი, 2 არქივი, 6 უმარაგო, 21 ფასდაკლებული):
  44/45 გაიარა

pagination:  5 გვერდი · db 59 · მიღწეული 59 · დუბლიკატი 0
             ვერმიღწეული: არცერთი · ზედმეტი: არცერთი
             ბოლოს მიღმა გვერდი → [] და 200

price_asc მართლა ზრდადია · price_desc მართლა კლებადი
კატეგორიის ფილტრი: api=15 db=15
ფასდაკლება: api=11 გამოთვლილი=11
არქივი → 404 · უცნობი slug → 404 · related საკუთარ თავს არ აბრუნებს
```

---

## 7. Search / Filtering — ✅ დახურულია (2026-09-12)

- [x] search მუშაობს — პროდუქტი სახელით მოიძებნება
- [x] search case-insensitive მუშაობს — ზედა და ქვედა რეგისტრი იდენტური
- [x] empty search სწორად მუშაობს — ცარიელი და მხოლოდ-ჰარეები = ფილტრის გარეშე
- [x] no results state არსებობს — 0 შედეგზე 200 და ცარიელი სია, არა შეცდომა
- [x] category filtering მუშაობს — api=15 db=15
- [x] product-specific filtering მუშაობს — brand, spec, toggle, price
- [x] filter + search ერთად მუშაობს — ავიწროებს, არ აფართოებს
- [x] filter reset მუშაობს — `clearFilters` სამივე ადგილას
- [x] **ცუდი query backend-ს არ ამტვრევს** — გასწორდა, იხ. ქვემოთ
- [x] search performance — trigram GIN ინდექსები `name`-სა და `search_text`-ზე

### რა გასწორდა

| # | პრობლემა | გასწორება |
|---|---|---|
| 🟡 | **`price=10-NaN` → HTTP 500.** `Decimal("NaN")` იქმნება, შედარება კი `try`-ს გარეთ იყო. `price=5-Infinity` კი შედარებას გაივლიდა და **ბაზამდე** აღწევდა. შვიდიდან ექვსი ჩავარდა | `is_finite()` + შედარება `try`-ში |
| 🟡 | `price=1e999999999-...` — სასრული, მაგრამ Postgres-ს არ ეტევა | ჭერზე მიჭრა (`Numeric(12,2)`-ის მაქსიმუმზე) |
| 🟢 | frontend `price=-50`-ს 0–50-ად კითხულობდა (`Number('')` = 0), სერვერი კი იგნორირებდა — გვერდითა პანელი აჩვენებდა ფილტრს, რომელიც შედეგებზე არ მოქმედებდა | ორივე მხარე ერთ წესზე |

⚠️ 500 **ავტორიზაციის გარეშე** იყო მიღწევადი, კატალოგის მთავარ endpoint-ზე,
ნებისმიერი სიხშირით.

### რა იყო უკვე ძლიერი

| | |
|---|---|
| **backend ↔ frontend ნორმალიზაციის პარიტეტი** | `normalize` და `tokenize` **261 query-ზე 0 განსხვავება** — ერთეულები, ათასეულები, ქართული სტემინგი, ტრანსლიტერაცია |
| **მტრული query-ები** | SQL injection, `%`, `_`, `\`, 2000 სიმბოლო, `<script>`, NUL, emoji — ყველა სუფთად დამუშავებული, კატალოგი ხელუხლებელი |
| **საზღვრები** | `q` > 200 → 400 · `page` < 1 → 400 · `limit` < 1 → 400 |

### გადამოწმების მტკიცებულება

```
search e2e: 22/23 გაიარა (ერთი ჩავარდნა ჩემი არასწორი პარამეტრი იყო — minPrice
            არ არსებობს, ფორმატია price=100-500)

ნორმალიზაციის პარიტეტი:  47 ხელით შედგენილი + 261 რეალური სახელი → 0 განსხვავება
ფასის ფილტრი გასწორების შემდეგ: 18 შემთხვევა → 0 ჩავარდნა
   1e400-1e500     → 0 პროდუქტი  (ყველა ფასზე მაღლა)
   0-1e999999999   → ყველა       (ყველა ფასის ქვემოთ)
```

12 ახალი ტესტი დამტკიცდა ბაგის დაბრუნებით — 9 backend-ზე, 3 frontend-ზე.

---

## 8. Cart — ✅ დახურულია (2026-09-12)

### Guest Cart
- [x] guest დამატება ავტორიზაციის გარეშე — კალათა ბრაუზერშია, სერვერი არ სჭირდება
- [x] quantity `+` / `-` მუშაობს — მარაგით შეზღუდული
- [x] remove მუშაობს — „დაბრუნების" საშუალებით
- [x] cart total სწორია — მთელი თეთრებით, backend-ს ზუსტად ემთხვევა
- [x] cart persists reload-ის შემდეგ — `localStorage`
- [x] unavailable product სწორად მუშავდება — backend უარყოფს, ქართულად

### Logged-in Cart
- [x] logged-in user-ის cart ინახება — **`carts` ცხრილი, თითო ანგარიშზე ერთი**
- [x] **cart database-თან სინქრონდება** — `GET/PUT/DELETE /cart`, `POST /cart/merge`
- [x] login-ის შემდეგ cart behavior — ორი კალათა ერწყმის, **დიდი რაოდენობა იმარჯვებს**
- [x] **logout-ის შემდეგ cart behavior** — ანგარიშზე ინახება, ბრაუზერში იწმინდება
- [x] სხვადასხვა device/session — ტელეფონზე დამატებული კომპიუტერზე ჩანს
- [x] cross-tab synchronization — `storage` event-ით
- [x] stock checkout-თან ხელახლა მოწმდება — სერვერზე, ატომურად

### რა გაკეთდა

| # | პრობლემა | გასწორება |
|---|---|---|
| 🟡 | უფასო მიწოდების ზღვარი float-ით ითვლებოდა — 195 883 კალათიდან 2 412 არასწორი | მთელი თეთრები |
| 🟡 | მყიდველი ინგლისურ შეცდომებს ხედავდა | `CODE_MESSAGES` შევსებული |
| 🟡 | **კალათა ბაზაში არ ინახებოდა** — მოწყობილობებს შორის იკარგებოდა, logout-ის შემდეგ კი ეკრანზე რჩებოდა | მიგრაცია `0009` + sync |

### გადაწყვეტილებები, რომლებიც სხვაგვარადაც შეიძლებოდა

| რა | რატომ ასე |
|---|---|
| **შერწყმისას დიდი რაოდენობა იმარჯვებს, არა ჯამი** | ტელეფონზე 2 კაბელი და ლეპტოპზე 2 — ეს ერთი ადამიანია, ვისაც 2 უნდა. შეკრება შეკვეთას ჩუმად გააორმაგებდა |
| **ინახება მხოლოდ `productId` და `qty`** | სახელი და ფასი კატალოგიდან იკითხება ყოველ ჯერზე — შენახული ფასი თვის შემდეგ ცრუ იქნებოდა |
| **`products`-ზე FK არ არის** | კალათა განზრახვის ჩანაწერია. წაშლილი პროდუქტი ერთ ხაზს აქრობს, არა მთელ კალათას |
| **logout ასუფთავებს ბრაუზერს** | უსაფრთხოა მხოლოდ იმიტომ, რომ ანგარიშზე უკვე შენახულია |

18 backend ტესტი + 6 frontend, ორივე დამტკიცებული ქცევის დაბრუნებით
(შეკრებაზე 3 ჩავარდა, logout-ის გაწმენდის მოხსნაზე 1).

---

## 9. Checkout — ✅ დახურულია (2026-09-12)

- [x] guest checkout მუშაობს — 201, შეკვეთის ნომრით
- [x] registered user checkout მუშაობს — იმავე გზით, `user_id`-ით
- [x] customer name validation — მინ. 2 სიმბოლო, ორივე ველზე
- [x] phone validation — `^5\d{8}$`, ქართული მობილური
- [x] city validation — მინ. 2
- [x] address validation — მინ. 5
- [x] comment field მუშაობს — ინახება, მაქს. 1000
- [x] payment method მუშაობს — **გასწორდა**, იხ. ქვემოთ
- [x] delivery information სწორად ინახება — jsonb snapshot-ად
- [x] invalid form submit არ ხდება — 10 შემთხვევა, ყველა 400
- [x] server-side validation არსებობს — `extra="forbid"` + Field-ები
- [x] **frontend price-ს backend არ ენდობა** — `price` ხაზში → 400
- [x] **backend ხელახლა ითვლის total-ს** — 80.00 + 5.00 = 85.00, სერვერზე
- [x] მიმდინარე ფასი გამოიყენება — snapshot შეკვეთის მომენტისაა
- [x] stock checkout-ზე ხელახლა მოწმდება — 409 + `available`
- [x] stock race condition ტესტირებულია — 8 concurrency ტესტი რეალურ Postgres-ზე
- [x] duplicate checkout protection — `Idempotency-Key`, უნიკალური ინდექსი
- [x] Idempotency-Key flow ტესტირებულია — გამეორება იმავე შეკვეთას აბრუნებს
- [x] failed checkout სწორად მუშავდება — rollback, მარაგი არ იხარჯება
- [x] successful checkout სრულდება — ledger-ის ჩანაწერით

### რა გასწორდა

| # | პრობლემა | გასწორება |
|---|---|---|
| 🟡 | **`payment_method` არსად არ მოწმდებოდა.** ნებისმიერი 32-სიმბოლოიანი სტრიქონი მიდიოდა request-იდან ადმინ პანელამდე. `paymentMethod: "already paid"` → **201** | `Literal` სქემაში + CHECK constraint (მიგრაცია `0010`) |
| 🟢 | `clear()` 800ms-ს ელოდებოდა — ტაბის დახურვისას ანგარიშზე ნაყიდი ნივთები რჩებოდა | მყისიერი `clearCart()` |

⚠️ პირველი **ჩემი კალათის ფუნქციამ** გააჩინა — მანამდე მიუწვდომელი იყო.

`payment_method`-ზე: ფულს არაფერი ამოძრავებს (ონლაინ გადახდა არ არსებობს), მაგრამ
შეკვეთების სიაში „already paid" კურიერს საქონლის უფასოდ გაცემას ნიშნავს.
`status`-ს enum პირველი მიგრაციიდან აქვს — ესეც იგივეა, მეორე ველზე, რომელზეც
ოპერატორი მოქმედებს.

### გადამოწმების მტკიცებულება

```
checkout e2e სუფთა ბაზაზე:  31/31

subtotal 80.00 · shipping 5.00 · total 85.00   ← სერვერზე
200.00 → უფასო მიწოდება
ხაზში price → 400 · totals სხეულში → 400
10 არასწორი ფორმა → ყველა 400
99 ცალი 3-ზე → 409 {"available": 2}
იგივე Idempotency-Key → იგივე შეკვეთა, მარაგი ერთხელ
არა-uuid key → 400 · ledger: ყოველ შეკვეთაზე ჩანაწერი
```

15 ახალი ტესტი, დამტკიცებული ბაგის დაბრუნებით (6 ჩავარდა, 2 frontend-ზე).

---

## 10. Orders — ✅ დახურულია (2026-09-12)

- [x] order იქმნება — 201, `VB-YYYYMMDD-NNNN`
- [x] order number უნიკალურია — sequence-იდან, 6 შეკვეთა → 6 ნომერი
- [x] order items სწორია
- [x] product snapshot სწორად ინახება — **ფასის შეცვლის შემდეგაც უცვლელი**
- [x] quantity სწორია
- [x] unit price სწორია — 40.00, შეკვეთის მომენტისა
- [x] total price სწორია — 80.00, სერვერზე გამოთვლილი
- [x] customer information სწორია
- [x] delivery information სწორია
- [x] payment method სწორია
- [x] order status იცვლება — მხოლოდ დაშვებული გადასვლებით
- [x] stock სწორად ცვლილდება — 10 → 8, ledger-ის ჩანაწერით
- [x] duplicate order არ იქმნება — `Idempotency-Key`
- [x] failed transaction rollback — მარაგი და მწკრივი ორივე ხელუხლებელი
- [x] user საკუთარ order-ებს ხედავს — 6/6
- [x] user სხვისას ვერ ხედავს — §3-ში დამტკიცებული
- [x] order details მუშაობს — მაღაზიაშიც და ადმინშიც

### 🟡 რა გასწორდა

**ადმინ პანელში ყველა შეკვეთას სახელის ნაცვლად „—" ეწერა.** ძებნა სახელითაც არ
მუშაობდა — შეკვეთის პოვნა მხოლოდ ნომრით ან ტელეფონით შეიძლებოდა.

```
ბაზაში ინახება  :  first_name, last_name     (model_dump() → ველების სახელები)
ადმინი კითხულობდა:  firstName, lastName       (API-ს camelCase alias-ები)
                    → None → "—"
```

⚠️ **არაფერი ჩავარდნილა** — მაღაზია უბრალოდ ვერ ხედავდა, ვინ შეუკვეთა.

**რატომ არ დაიჭირეს ტესტებმა:** ისინი snapshot-ს `create_order`-ის პირდაპირი
გამოძახებით აწყობდნენ, camelCase-ით — ანუ ფიქსტურა production-ს არ ემთხვეოდა და
ძველი კოდი სატესტო მონაცემებზე *სწორი* იყო.

გასწორდა ორივე მხარე: ფიქსტურა რეალობას მიუსადაგდა, და 3 ახალი ტესტი შეკვეთას
**API-ით** ათავსებს და ადმინის API-ით კითხულობს. ერთი მათგანი გასაღებების
სახელებს პირდაპირ ამოწმებს, რომ ნებისმიერი მხარის ცვლილება ხმაურიანი იყოს.

ეს ბაგი **პასუხის სხეულის წაკითხვით** ვიპოვე e2e-ში, არა ჩავარდნილი ტესტით.

### გადამოწმების მტკიცებულება

```
orders e2e სუფთა ბაზაზე:  37/37

stock 10 → 8 · ledger: order_placed −2
ფასი 40 → 999 შეიცვალა → შეკვეთაში ისევ 40.00
6 შეკვეთა → 6 უნიკალური ნომერი
ჩავარდნილი შეკვეთა → მარაგი და მწკრივი უცვლელი
სტუმრის lookup: სწორი ტელეფონით 200, არასწორით 404
გაუქმება → მარაგი დაბრუნდა, ledger: order_cancelled
ორჯერ გაუქმება → მარაგი ერთხელ
უცნობი სტატუსი → 400 · pending → delivered → 409 · pending → confirmed → 200
```

⚠️ **მცირე შენიშვნა:** `order_number`-ის ბოლო 4 ციფრი `seq % 10000`-ია. ერთ დღეში
10 000-ზე მეტი შეკვეთა ნომრის გამეორებას გამოიწვევდა — `uq_orders_order_number`
ამას 500-ით დაიჭერდა. ამ მაღაზიისთვის მიუღწეველია, მაგრამ ჩაწერილია.

---

## 11–25 — ⬜ ჯერ არ დაწყებულა

`11. Admin Panel` · `12. Order Status / Business Flow` · `13. Error Handling` ·
`14. Performance` · `15. SEO` · `16. Accessibility` · `17. Responsive / Browser` ·
`18. Full E2E` · `19. Testing / CI` · `20. Logging / Monitoring` ·
`21. Backup / Recovery` · `22. Payment` · `23. Analytics` ·
`24. Domain / Deployment` · `25. Final Launch`

პუნქტები სრული სახით — `voltbox_pre_deployment_checklist.md` (საწყისი დოკუმენტი).

---

## Release Gate

deployment-მდე ყველა უნდა იყოს ✅:

Authentication · Authorization · Database · Products · Cart · Checkout ·
Orders · Stock · Admin · Security · Error handling · Tests · Production build ·
Backup · Monitoring · HTTPS · Domain · Final E2E

გაშვების შემდეგ შეიძლება: Wishlist · Reviews · Product comparison ·
Recently viewed · Promo codes · Advanced analytics · Recommendations
