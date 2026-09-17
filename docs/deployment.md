# Deployment — რა უნდა დაყენდეს და რა ტყდება, თუ არ დაყენდა

ეს დოკუმენტი პრე-დეპლოიმენტის აუდიტის (§0–§24) ყველა გადადებულ პუნქტს კრებს
ერთად. **თითოეულს ახლავს პასუხი კითხვაზე „რა მოხდება, თუ დამავიწყდება".**

არქიტექტურა: ორი ცალკე სერვისი.

```
frontend  →  სტატიკური საიტი (Vite-ის dist/)
backend   →  Docker, gunicorn + uvicorn worker-ები
ბაზა      →  Supabase PostgreSQL 17.6, eu-central-1
```

---

## 🔴 1. SPA-ს rewrite — ყველაზე მნიშვნელოვანი

**გაზომილი, არა ნავარაუდევი.** სტატიკური ჰოსტი rewrite-ის წესის გარეშე:

```
/                        200
/product/anker-nano-20w  404   ←
/category/phones         404   ←
/admin                   404   ←
```

მაღაზია მთავარ გვერდზე იმუშავებს და **ყველა გაზიარებული ბმული მკვდარი
იქნება** — Facebook-ზე დადებული პროდუქტიც, გვერდის განახლებაც.

React Router მარშრუტს ბრაუზერში ხსნის, მაგრამ მხოლოდ მას შემდეგ, რაც
`index.html` ჩაიტვირთება. ჰოსტს უნდა ვუთხრათ, რომ უცნობ მისამართზე ის გასცეს.

**Rule-ი `frontend/render.yaml`-შია — პანელში ხელით არ ემატება:**

| Source | Destination | Action |
|---|---|---|
| `/*` | `/index.html` | **Rewrite** |

⚠️ `Redirect` **არა** — `Rewrite`. Redirect მისამართს შეცვლის და ბმული
დაიკარგება.

### Blueprint-ის შექმნა

ფაილი repo-ს ძირში არ არის, ამიტომ Render მას თვითონ ვერ იპოვის:

**Render → New → Blueprint → Blueprint Path: `frontend/render.yaml`**

შექმნისას Render `VITE_API_BASE_URL`-ს და `VITE_SITE_URL`-ს იკითხავს (§3) —
**მხოლოდ ამ ერთხელ**, შემდეგი sync-ები მათ აღარ ეხება.

sync-ისას ფაილში ჩამოთვლილი rule-ები და header-ები პანელის ვერსიას
**გადააწერს**, პანელში დამატებული დანარჩენი რჩება. **ცვლილება — ფაილში, არა
პანელში**, თორემ შემდეგი sync-ი მას ჩუმად დააბრუნებს.

### ⚠️ CSP-ის placeholder-ი

`Content-Security-Policy`-ში ერთ მნიშვნელობა განზრახ ცარიელია — Supabase
Storage-ის origin-ი, საიდანაც პროდუქტის სურათები მოდის:

| Placeholder | რა ჩაიწერება | რა მოხდება, თუ დამავიწყდება |
|---|---|---|
| `<SUPABASE_STORAGE_ORIGIN>` | API-ს დაბრუნებული სურათის URL-ის scheme + host, path-ის გარეშე | ბრაუზერი token-ს უგულებელყოფს და **ყველა პროდუქტის სურათს დაბლოკავს** |

API-ს origin-ი (`https://api.voltbox.ge`) `connect-src`-ში უკვე წერია და
`VITE_API_BASE_URL`-ის origin-ს **უნდა ემთხვეოდეს** — თორემ ყველა API-მოთხოვნა
ბლოკდება.

გაშვებამდე:

```bash
grep -v '^\s*#' frontend/render.yaml | grep -oE '<[A-Z_]+>'
```

ახლა ერთ ხაზს აჩვენებს — `<SUPABASE_STORAGE_ORIGIN>`. **deploy-ამდე ცარიელი
უნდა იყოს.**

---

## 2. Backend-ის environment

| ცვლადი | მნიშვნელობა | რა მოხდება, თუ არასწორია |
|---|---|---|
| `APP_ENV` | `production` | **სერვერი არ აიწევს.** დაუყენებლად: `/docs` საჯარო, cookie `Secure`-ის გარეშე, storage მეხსიერებაში |
| `DATABASE_URL` | Supabase-ის pooler-ის URL | სერვისი ვერ აიწევს |
| `JWT_SECRET` | **ახალი**, ≥32 სიმბოლო | ძველი ტოკენები ძალაში დარჩება |
| `FORWARDED_ALLOW_IPS` | proxy-ის მისამართი | **სერვერი არ აიწევს.** `*`-იც უარყოფილია — მაშინ ნებისმიერს შეუძლია თავისი IP აირჩიოს |
| `TRUSTED_HOSTS` | `api.voltbox.ge,<service>.onrender.com` | **სერვერი არ აიწევს** `*`-ზე ან ცარიელზე. API-ს host-ი — storefront-ის დომენი **არა**. მის გარეშე ყველა მოთხოვნა, health-იც, `400 Invalid host header`-ს აბრუნებს, და შეცდომა `TRUSTED_HOSTS`-ს არ ახსენებს. ↓ იხ. TRUSTED_HOSTS |
| `CORS_ORIGINS` | `https://voltbox.ge` | **სერვერი არ აიწევს** ცარიელზე, `*`-ზე ან local origin-ზე (`localhost`, `127.0.0.1`, `::1`). საჯარო, მაგრამ არასწორ origin-ზე აიწევს — და ბრაუზერი მოთხოვნებს დაბლოკავს |
| `SITE_URL` | `https://voltbox.ge` | sitemap-ის ბმულები არასწორ დომენზე მიუთითებს |
| `REDIS_URL` | Redis-ის URL | **სერვერი არ აიწევს**, თუ worker-ი >1. counter-ები worker-ებად გაიყოფა და ლიმიტი გამრავლდება |
| `SUPABASE_PROJECT_REF` | პროექტის ref | სურათების ატვირთვა ჩავარდება (production-ში `RuntimeError`) |
| `SUPABASE_SERVICE_ROLE_KEY` | service role key | იგივე |
| `WEB_CONCURRENCY` | 2 | ↓ იხ. კავშირების ბიუჯეტი |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 5 / 5 | **სერვერი არ აიწევს**, თუ `worker × (pool+overflow)` ბიუჯეტს გადააჭარბებს |

### ⚠️ TRUSTED_HOSTS — API-ს host-ი, არა storefront-ის

`TRUSTED_HOSTS` API-ზე მოსული მოთხოვნის **`Host`** header-ს ამოწმებს. storefront-იდან
ბრაუზერი აგზავნის `Host: api.voltbox.ge` და `Origin: https://voltbox.ge` —
`Origin`-ი `CORS_ORIGINS`-ის საქმეა. `voltbox.ge`-ზე მოთხოვნები static site-ზე
მიდის და API-ს არასდროს მიაღწევს, ამიტომ storefront-ის დომენს აქ არაფერი აქვს.

გაზომილი: `TRUSTED_HOSTS=voltbox.ge,www.voltbox.ge` → `api.voltbox.ge` →
**400 Invalid host header**.

**Render-ის health check-ი.** HTTP health check-ს Render custom domain-ის
`Host`-ით აგზავნის, *თუ domain-ი verify-ებულია*; მანამდე — service-ის
`onrender.com` subdomain-ით. ეს subdomain-ი service-ის სახელს შეიცავს, მაგრამ
მასთან ტოლობა გარანტირებული არ არის — ის **შექმნის შემდეგ** dashboard-ში ჩანს.
თუ check-ი 400-ს მიიღებს, Render deploy-ს 15 წუთში გააუქმებს, და შეცდომა
`TRUSTED_HOSTS`-ს არ ახსენებს. ამიტომ რიგი:

1. service-ის შექმნისას `TRUSTED_HOSTS=api.voltbox.ge`, **Health Check Path —
   ცარიელი**. default-ი TCP probe-ია, `Host`-ს არ ამოწმებს — პირველ deploy-ი
   გაივლის.
2. შექმნის შემდეგ onrender.com-ის hostname-ი dashboard-იდან:
   `TRUSTED_HOSTS=api.voltbox.ge,<service>.onrender.com`
3. **მხოლოდ მერე** — Settings → Health Checks → `/api/v1/health`. domain-ის
   verification-ამდეც და შემდეგაც `Host` სიაში იქნება.
4. შემოწმება:

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://<service>.onrender.com/api/v1/health   # 200; 400 = ნაბიჯ 2 გამორჩა
   ```

onrender.com-ის hostname-ი Host-ის შემოწმებას **არ ასუსტებს**. ეს Render-ის
host-ია, რომელზეც Render **ეს** service-ი ისედაც გასცემს — custom domain-ის
დამატების შემდეგაც — და სხვაგან მიუთითება შეუძლებელია. სია ჩაკეტილი რჩება:
ნებისმიერი სხვა `Host` ისევ 400-ს აბრუნებს. თუ API onrender.com-ზე საერთოდ არ
უნდა ჩანდეს, ეს ცალკე გადაწყვეტილებაა — Settings → Custom Domains → Render
Subdomain → Disabled (custom domain-ს ითხოვს).

### ⚠️ კავშირების ბიუჯეტი

Supabase-ის `max_connections` = **60**, საიდანაც 3 superuser-ისთვისაა და ~20
Supabase-ის საკუთარ სერვისებს უჭირავს.

```
2 worker × (5 + 5) = 20 კავშირი   ✅
4 worker × (10 + 10) = 80         ❌ სერვერი უარს იტყვის აწევაზე
```

### JWT_SECRET-ის გენერაცია

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**ახალი უნდა იყოს.** დეველოპმენტის დროინდელი გასაღები ლოკალურ `.env`-შია და
იმავე გასაღებით ხელმოწერილი ტოკენი production-ზეც იმუშავებდა.

### Cron job — ვადაგასული refresh-ტოკენების წაშლა

ყოველი refresh `refresh_tokens`-ში ახალ მწკრივს წერს.
`scripts/prune_refresh_tokens.py` შლის მწკრივებს, რომლების ვადაც 7 დღეზე მეტი
ხნის წინ გავიდა. რატომ ზუსტად ასე — `ASSUMPTIONS.md` 8.13.

**Render → New → Cron Job**, იმავე repo-თი და Dockerfile-ით (`backend/`), რაც
backend-ის web service-ი:

| ველი | მნიშვნელობა |
|---|---|
| Schedule | `0 23 * * *` — Render-ის cron-ი UTC-ზეა, ეს 03:00 თბილისით |
| Docker Command (Advanced) | `python scripts/prune_refresh_tokens.py` |
| Environment | `DATABASE_URL` და `JWT_SECRET` — Environment Group-იდან, რომელიც web service-ზეც linked-ია |

Environment Group-ი იმისთვისაა, რომ შეცვლილი პაროლი job-ს უკან არ დატოვებს:
job-ზე ცალკე ჩაწერილი `DATABASE_URL` პაროლის შემდეგ rotation-ზე ძველი
დარჩებოდა, და job-ი ყოველ ღამე ჩავარდნდა. `JWT_SECRET` job-ს არ სჭირდება,
მაგრამ Settings-ი მის გარეშე არ აიწევს. კავშირი ერთია, წამებით, ↑ ბიუჯეტს არ
ცვლის.

**რა მოხდება, თუ დამავიწყდება:** არაფერი ტყდება. `refresh_tokens` ყოველ
refresh-ზე ერთ მწკრივით იზრდება — ზღვრის გარეშე, 500 MB-ისკენ.

**რა მოხდება, თუ job-ი ჩავარდა:** Render-ის docs failure-notification-ს არ
აღწერს — ჩავარდნა მხოლოდ job-ის **Runs** გვერდზე ჩანს. გამორჩენილი run-ი წაშლას
მხოლოდ აგვიანებს: ნაადრევ წაშლა შეუძლებელია, და შემდეგი run-ი ეწევა.

**შემოწმება:**

1. **Runs → Trigger Run** — log-ში:

   ```
   refresh_tokens: deleted N rows expired more than 7 days ago
   ```

2. job-ის ერთ დღის მუშაობის შემდეგ, SQL Editor-ში:

   ```sql
   select count(*) from public.refresh_tokens
   where expires_at < now() - interval '9 days';   -- 0
   ```

   7 — retention, +1 — დღიური ინტერვალი, +1 — run-ის დაგვიანების ზღვარი.
   0-ზე მეტი ნიშნავს, რომ job-ი არ ეშვება. `public.` სავალდებულოა (§5).

ცოცხალ ბაზაზე პირველი ხელით გაშვება — `--dry-run`-ით: ითვლის, არაფერს შლის.

```bash
cd backend
python scripts/prune_refresh_tokens.py --dry-run   # DATABASE_URL — .env-იდან
```

---

## 3. Frontend-ის build

ეს **ბილდის დროს** იკითხება, არა გაშვებისას — შეცვლის შემდეგ ხელახლა ბილდი.

`VITE_API_MODE=http` `frontend/render.yaml`-შია. დანარჩენ ორს Render
Blueprint-ის შექმნისას **ერთხელ** იკითხავს (§1); შემდეგ — სერვისის
Environment-ის გვერდიდან.

| ცვლადი | მნიშვნელობა | რა მოხდება, თუ არასწორია |
|---|---|---|
| `VITE_API_MODE` | `http` | **მაღაზია 61 სატესტო პროდუქტს აჩვენებს** მეხსიერებიდან და შეკვეთა არსად წავა |
| `VITE_API_BASE_URL` | `https://api.voltbox.ge/api/v1` | ვერცერთი მოთხოვნა ვერ გავა. origin-ი CSP-ის `connect-src`-ს უნდა ემთხვეოდეს (§1) |
| `VITE_SITE_URL` | `https://voltbox.ge` | canonical და გაზიარების სურათი `localhost:5173`-ზე მიუთითებს |

`VITE_SITE_URL`-ის დაუყენებლობა ბილდს არ ტეხს — Vite გაფრთხილებას დაბეჭდავს
და `localhost`-ს ჩასვამს. **გაფრთხილება ბილდის ლოგშია, შეამოწმეთ.**

---

## 4. robots.txt და sitemap

`frontend/public/robots.txt`-ის ბოლო ხაზი გაუკომენტარეთ და დომენი ჩასვით:

```
Sitemap: https://api.voltbox.ge/sitemap.xml
```

sitemap-ს **API გასცემს**, რადგან მხოლოდ მან იცის, რა არის კატალოგში. crawler-ს
ერთი დომენი ურჩევნია, ამიტომ სტატიკური ჰოსტი მას საკუთარ დომენზე გასცემს —
rule-ი `frontend/render.yaml`-შია:

| Source | Destination | Action |
|---|---|---|
| `/sitemap.xml` | `https://api.voltbox.ge/sitemap.xml` | Rewrite |

⚠️ `/*`-ის **ზემოთ**. Render rule-ებს ზემოდან ქვემოთ ამოწმებს და პირველ
დამთხვეულს იყენებს; ქვემოთ დარჩენილს `/*` გადაფარავს, და crawler-ი sitemap-ის
ნაცვლად `index.html`-ს მიიღებს — 200-ით, შეცდომის გარეშე.

მერე Google Search Console-ში: დომენის დადასტურება და sitemap-ის გაგზავნა.

---

## 5. მიგრაციები

⚠️ **`alembic upgrade` პირდაპირ არ გაუშვათ Supabase-ზე** — SQL Editor-ით
გაკეთდა ყველა წინა. მიზეზი: GoTrue-ს საკუთარი `auth.refresh_tokens` აქვს,
რომელიც ჩვენსას ჩრდილავს, ამიტომ **ყველა ბრძანება `public.`-ით უნდა იყოს
დაკვალიფიცირებული**.

```bash
cd backend
alembic upgrade <ძველი>:<ახალი> --sql > migration.sql
# ხელით დაამატეთ public. ყველა ცხრილის სახელს, მერე SQL Editor-ში
```

ამჟამად ბაზა `0010`-ზეა, კოდი — `0011`-ზე. `0011` მხოლოდ ინდექსს ამატებს
`refresh_tokens.expires_at`-ზე (§2, cron job): მის გარეშე prune-ი მუშაობს,
ოღონდ ცხრილს მთლიანად scan-ავს, და `alembic check` Supabase-ზე drift-ს აჩვენებს.

---

## 6. პირველი ადმინი

```bash
VOLTBOX_ADMIN_PASSWORD='...' python scripts/manage_admin.py create-admin \
  --email you@example.ge --first-name სახელი --last-name გვარი
```

პაროლი **არგუმენტად არასდროს** — ის shell-ის ისტორიაში, `ps`-ში და CI-ის
ლოგში რჩება.

ეს ნაბიჯი უკვე შესრულებულია. ⚠️ კონკრეტული მისამართი აქ განზრახ არ წერია:
ეს repo საჯაროა, და ადმინის ელფოსტა მომხმარებლის სახელიცაა.

---

## 7. HTTPS

ჰოსტის საქმეა (Render-ს ავტომატური სერტიფიკატი აქვს). აპლიკაცია HSTS-ს
თვითონ აგზავნის, როცა `APP_ENV` = `production` ან `staging`:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

`preload` განზრახ არაა — ის დომენის მთელი ხის გადაწყვეტილებაა და პრაქტიკულად
შეუქცევადი.

---

## 8. Backup

🔴 **Supabase Free Plan-ს backup არ აქვს** — არც scheduled, არც PITR.
გადაწყვეტილება გაშვებამდე: `docs/backup-restore.md`.

ბაზაში უკვე დევს ხელით შეყვანილი სამუშაო (ადმინი, კატეგორიები, ბრენდები,
პროდუქტი), რომელიც მიგრაციებში არაა.

---

## 9. მონიტორინგი

`/api/v1/health` მზადაა. უფასო uptime-სერვისი (UptimeRobot, Better Stack)
5 წუთში ეყენება და 500-ების ან გათიშვის შემთხვევაში შეგატყობინებთ.

Render-ის საკუთარი Health Check Path-ი — ⚠️ **§2-ის TRUSTED_HOSTS-ის ნაბიჯ 2-ის
შემდეგ, არა ადრე.**

ლოგი `stdout`-შია, JSON-ად — Render აგროვებს და ძებნა აქვს.

---

## 10. გაშვების შემდეგ — გადამოწმება

```bash
# ღრმა ბმული — თუ ეს 404-ია, rewrite არ მუშაობს
curl -s -o /dev/null -w '%{http_code}\n' https://voltbox.ge/product/<slug>

# storefront-ის header-ები — ღრმა ბმულზე, rewrite-ით გაცემულ პასუხზე
curl -sI https://voltbox.ge/product/<slug> | grep -iE 'content-security|x-frame|x-content-type|referrer-policy'

# sitemap საკუთარ დომენზე — XML, არა index.html
curl -sI https://voltbox.ge/sitemap.xml | grep -i content-type
curl -s https://voltbox.ge/sitemap.xml | head -c 200      # <?xml ... <urlset

# API ცოცხალია
curl -s https://api.voltbox.ge/api/v1/health

# /docs დახურულია
curl -s -o /dev/null -w '%{http_code}\n' https://api.voltbox.ge/docs      # 404

# HSTS და უსაფრთხოების header-ები
curl -sI https://api.voltbox.ge/api/v1/health | grep -iE 'strict-transport|x-content-type|x-frame'

# sitemap-ში პროდუქტები ჩანს
curl -s https://api.voltbox.ge/sitemap.xml | grep -c '<loc>'

# გაზიარების ბარათი სწორ დომენზე
curl -s https://voltbox.ge | grep 'og:image'
```

მერე სრული E2E ცოცხალ დომენზე: `backend/scripts/e2e/journey.py`-ის
მისამართები შეცვალეთ და გაუშვით — ან ხელით გაიარეთ შეკვეთა თავიდან ბოლომდე.

---

## 11. რასაც ავტომატიკა ვერ დაიჭერს

- **რეალურ ტელეფონზე გავლა** — ღილაკები, ფოკუსი, კლავიატურა
- **სკრინრიდერით შემოწმება**
- **პროდუქტის preview გაზიარებისას** — მესამე მხარის crawler-ები JS-ს არ
  უშვებენ, ამიტომ ყველა ბმული მაღაზიის საერთო ბარათს აჩვენებს (§15)
