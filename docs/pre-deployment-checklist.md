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

## 3. Authentication — ⬜

### Register
- [ ] ახალი user-ის რეგისტრაცია მუშაობს — *(§0-ში 201 დადასტურდა)*
- [ ] email validation მუშაობს
- [ ] duplicate email სწორად მუშავდება
- [ ] password validation მუშაობს
- [ ] password უსაფრთხოდ hash-დება
- [ ] არასწორ input-ზე error სწორად ბრუნდება

### Login
- [ ] სწორი login მუშაობს — *(§0-ში 200 დადასტურდა)*
- [ ] არასწორი password სწორად ბრუნდება
- [ ] არარსებული user სწორად მუშავდება
- [ ] access token/session flow მუშაობს
- [ ] refresh token flow მუშაობს — *(§0-ში 200 დადასტურდა)*
- [ ] refresh token უსაფრთხოდ ინახება — *(§0: httpOnly, path=/api/v1/auth)*
- [ ] logout მუშაობს — *(§0-ში 200 → 401 დადასტურდა)*
- [ ] expired session სწორად მუშავდება
- [ ] refresh token rotation/invalidation მუშაობს — *(§0: ოჯახები დადასტურდა)*

### Authorization
- [ ] ჩვეულებრივი user ვერ შედის admin API-ზე
- [ ] ჩვეულებრივი user ვერ ასრულებს admin action-ს
- [ ] user-ს სხვისი მონაცემების ნახვა არ შეუძლია
- [ ] user-ს სხვისი order-ის ნახვა არ შეუძლია
- [ ] backend authorization გადამოწმებულია
- [ ] frontend route protection გადამოწმებულია

---

## 4. Security Audit — ⬜

- [ ] HTTPS გამოყენებისთვის მზადაა
- [ ] CORS production configuration სწორია — *(§0: default localhost, დაცვის გარეშე)*
- [ ] rate limiting ჩართულია — *(§0: `REDIS_URL` ცარიელია → per-worker მთვლელები)*
- [ ] forwarded IP / proxy configuration სწორია — *(`gunicorn.conf.py` production-ში ამოწმებს)*
- [ ] brute-force protection შემოწმებულია
- [ ] input validation ყველა endpoint-ზე მუშაობს
- [ ] SQL injection-ის რისკი შემოწმებულია
- [ ] XSS-ის რისკი შემოწმებულია
- [ ] CSRF-ის საჭიროება/დაცვა შემოწმებულია
- [ ] sensitive data response-ში არ ხვდება
- [ ] stack trace production response-ში არ ხვდება — *(§0-ში დადასტურდა)*
- [ ] debug mode გამორთულია
- [ ] admin endpoints დაცულია
- [ ] security headers განახლებულია
- [ ] dependency security audit შესრულებულია
- [ ] მოძველებული / vulnerable dependency-ები განახლებულია
- [ ] secrets rotation საჭიროებაზე შემოწმებულია

---

## 5–25 — ⬜ ჯერ არ დაწყებულა

`5. Product Management` · `6. Product Page / Catalog` · `7. Search / Filtering` ·
`8. Cart` · `9. Checkout` · `10. Orders` · `11. Admin Panel` ·
`12. Order Status / Business Flow` · `13. Error Handling` · `14. Performance` ·
`15. SEO` · `16. Accessibility` · `17. Responsive / Browser` · `18. Full E2E` ·
`19. Testing / CI` · `20. Logging / Monitoring` · `21. Backup / Recovery` ·
`22. Payment` · `23. Analytics` · `24. Domain / Deployment` · `25. Final Launch`

პუნქტები სრული სახით — `voltbox_pre_deployment_checklist.md` (საწყისი დოკუმენტი).

---

## Release Gate

deployment-მდე ყველა უნდა იყოს ✅:

Authentication · Authorization · Database · Products · Cart · Checkout ·
Orders · Stock · Admin · Security · Error handling · Tests · Production build ·
Backup · Monitoring · HTTPS · Domain · Final E2E

გაშვების შემდეგ შეიძლება: Wishlist · Reviews · Product comparison ·
Recently viewed · Promo codes · Advanced analytics · Recommendations
