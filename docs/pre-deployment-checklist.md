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

## 1. Database / Supabase — ⬜

- [ ] Production database სწორად შექმნილია
- [ ] ყველა migration სწორად გაშვებულია
- [ ] database schema სრულად განახლებულია
- [ ] ყველა foreign key შემოწმებულია
- [ ] ყველა საჭირო unique constraint შემოწმებულია
- [ ] ყველა საჭირო index შემოწმებულია
- [ ] Product მონაცემები სწორად ინახება
- [ ] Category მონაცემები სწორად ინახება
- [ ] User მონაცემები სწორად ინახება
- [ ] Order მონაცემები სწორად ინახება
- [ ] Cart მონაცემები სწორად ინახება
- [ ] Stock მონაცემები სწორად ცვლილდება
- [ ] concurrent order / stock შემცირება ტესტირებულია
- [ ] transaction boundaries შემოწმებულია
- [ ] connection/pool configuration შემოწმებულია
- [ ] production backup ჩართულია
- [ ] backup restore პროცედურაც ტესტირებულია

---

## 2. Environment Variables / Secrets — ⬜

- [ ] Development და Production environment-ები გამიჯნულია
- [ ] ყველა საჭირო env variable ჩამოწერილია
- [ ] production secrets GitHub-ში არ არის
- [ ] `.env` ფაილები repository-ში არ არის — *(ნაწილობრივ: §0-ში frontend/.env მოიხსნა)*
- [ ] API keys დაცულია
- [ ] JWT/session secrets დაცულია
- [ ] database credentials დაცულია
- [ ] frontend-ში secret მნიშვნელობები არ ხვდება
- [ ] production configuration values განახლებულია

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
