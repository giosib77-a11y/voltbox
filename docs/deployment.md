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

## 0. სატესტო deploy — Render Free, დომენის გარეშე

`voltbox.ge`-ის ყიდვამდე ორივე Blueprint Render-ის უფასო tier-ზეა, onrender.com-ის
მისამართებით. API — `plan: free` (`backend/render.yaml`), 0.1 CPU და 512 MB.

**ლიმიტები (Render-ის docs, `render.com/docs/free`):**

- უფასო web service-ი **15 წუთი მოთხოვნის გარეშე იძინებს**. შემდეგი მოთხოვნა
  მის გაღვიძებას **დაახლოებით ერთ წუთს ელოდება** — მაღაზიის პირველი გახსნა
  დიდი ხნის შემდეგ პროდუქტებს წუთით აგვიანებს. ეს შეცდომა არ არის.
- workspace-ს თვეში 750 უფასო საათი აქვს — ერთ სერვისს მთელი თვე ჰყოფნის.
- **cron job-ი უფასო არ არსებობს** — refresh-ტოკენების წაშლა ფაილიდან ამოღებულია
  (§2, Cron job). ფასიანზე გადასვლისას **უკან ბრუნდება**, `plan`-თან ერთად
  (`0.5c-512mb`).
- Health Check Path უფასოზეც მუშაობს — Render-ის უფასოს შეზღუდვების სიაში ის არ
  არის — და ფაილში რჩება.

**დომენამდე onrender.com-ზე მიუთითებს.** სახელებს Render სერვისის შექმნისას
აძლევს (დაკავებულ სახელს სუფიქსს უმატებს). API — `https://voltbox-api.onrender.com`;
storefront-ი ჯერ შექმნილი არ არის — `https://voltbox-storefront.onrender.com`
მხოლოდ მაშინ, თუ სახელი თავისუფალია; სხვა მისამართის შემთხვევაში ქვემოთ
storefront-ის ორი მნიშვნელობა ისევ იცვლება. ყველაფერი Blueprint-ის ფაილებშია —
იცვლება კოდში, არა პანელში, რომელსაც შემდეგი sync-ი გადააწერს:

| სად | დომენამდე | დომენის შემდეგ |
|---|---|---|
| `CORS_ORIGINS` (`backend/render.yaml`) | `https://voltbox-storefront.onrender.com` | `https://voltbox.ge` |
| `SITE_URL` (`backend/render.yaml`) | `https://voltbox-storefront.onrender.com` | `https://voltbox.ge` |
| `connect-src` (`frontend/render.yaml`) | `https://voltbox-api.onrender.com` | `https://api.voltbox.ge` |
| `/sitemap.xml`-ის rewrite (`frontend/render.yaml`) | `https://voltbox-api.onrender.com/sitemap.xml` | `https://api.voltbox.ge/sitemap.xml` |
| `Strict-Transport-Security` (`frontend/render.yaml`) | `max-age=300` | `max-age=31536000` |
| `TRUSTED_HOSTS` | ცვლილება არ სჭირდება: `voltbox-api.onrender.com`-ს აპი `RENDER_EXTERNAL_HOSTNAME`-იდან თვითონ უმატებს (§2) | `api.voltbox.ge` — უკვე ასეა |

თითოეულ დროებით მნიშვნელობას ფაილში `TEMP-ONRENDER` კომენტარი ახლავს —
დომენის ყიდვის შემდეგ ყველა ერთი ძებნით იპოვება:

```bash
grep -rn TEMP-ONRENDER backend/render.yaml frontend/render.yaml
```

storefront-ის Blueprint-ის შექმნისას Render იკითხავს (§3):
`VITE_API_BASE_URL=https://voltbox-api.onrender.com/api/v1` — origin-ი
`connect-src`-ს უნდა ემთხვეოდეს — და
`VITE_SITE_URL=https://voltbox-storefront.onrender.com`. ეს ორი ფაილში არ წერია,
ამიტომ დომენის შემდეგ პანელში იცვლება და ახალ deploy-ს სჭირდება.

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

### ⚠️ CSP-ის origin-ები

`Content-Security-Policy` ორ გარე origin-ს ასახელებს:

| სად | მნიშვნელობა | რა მოხდება, თუ არ ემთხვევა |
|---|---|---|
| `img-src` | `https://jnfokdczfpcysnqiwask.supabase.co` — Supabase პროექტის საჯარო URL-ი, ყველა პროდუქტის სურათის ბმულში (საიდუმლო არ არის) | ბრაუზერი **ყველა პროდუქტის სურათს დაბლოკავს**. სხვა Supabase პროექტი = სხვა host-ი აქ |
| `connect-src` | `https://api.voltbox.ge` (დომენამდე `https://voltbox-api.onrender.com`, §0) | `VITE_API_BASE_URL`-ის origin-ს **უნდა ემთხვეოდეს** — თორემ ყველა API-მოთხოვნა ბლოკდება |

გაშვებამდე — placeholder-ი ფაილში აღარ უნდა დარჩეს:

```bash
grep -v '^\s*#' frontend/render.yaml | grep -oE '<[A-Z_]+>'
```

**ცარიელი უნდა იყოს.**

---

## 2. Backend-ის environment

API `backend/render.yaml`-შია: region (`frankfurt` — Supabase-ის გვერდით;
შექმნის შემდეგ აღარ იცვლება), plan, Dockerfile, **Health Check Path** და ის
ცვლადები, რომლებიც საიდუმლო არ არის. refresh-ტოკენების cron job-ი უფასო plan-ზე
ფაილიდან ამოღებულია — ↓ Cron job.

### Blueprint-ის შექმნა

**Render → New → Blueprint → Blueprint Path: `backend/render.yaml`**

ცალკე Blueprint-ია, `frontend/render.yaml`-თან ერთ ფაილში არ არის: ორ სერვისს
ერთმანეთისთვის გადასაცემი მნიშვნელობა არ აქვს — ერთმანეთის საჯარო მისამართებს
Blueprint ვერ გადასცემს და ორივე მხარეს ისედაც ხელით წერია.

1. შექმნისას Render იკითხავს `JWT_SECRET`-ს, `FORWARDED_ALLOW_IPS`-ს,
   `REDIS_URL`-ს, `SUPABASE_PROJECT_REF`-ს და `SUPABASE_SERVICE_ROLE_KEY`-ს —
   **მხოლოდ ამ ერთხელ**, შემდეგი sync-ები მათ აღარ ეხება.
2. `DATABASE_URL`-ს **არ იკითხავს**. ის Environment Group-შია —
   `voltbox-database`, რომელსაც Blueprint ცარიელს ქმნის და API-ს (cron job-ის
   დაბრუნების შემდეგ — job-საც) უკავშირებს. group-ში `sync: false`-ს Render ჩუმად უგულებელყოფს, ამიტომ
   ფაილში ვერ ჩაიწერება. API-ს პირველი deploy `DATABASE_URL`-ის გარეშე
   **ჩავარდება — ეს მოსალოდნელია**. შემდეგ: Environment Groups →
   `voltbox-database` → `DATABASE_URL` → შენახვა ახალ deploy-ს იწყებს.
3. Telegram-ის და ელფოსტის ცვლადები ფაილში არ არის (არასავალდებულოა) — ↓ იხ.
   Telegram და ელფოსტა.

sync-ისას ფაილში დაწერილი მნიშვნელობები პანელისას **გადააწერს** — Health
Check Path-ს, `TRUSTED_HOSTS`-ს, `CORS_ORIGINS`-ს, `SITE_URL`-ს, plan-ს.
**ცვლილება — ფაილში, არა პანელში.** ფაილში დაუსახელებელ ცვლადებს sync არ ეხება.

`backend/tests/test_render_blueprint.py` ჩავარდება, თუ health path
`/api/v1/health/live` აღარ არის, თუ secret-ს ფაილში მნიშვნელობა ეწერება, თუ
group-ში `sync: false` გაჩნდება, ან თუ ფაილის მნიშვნელობებს `gunicorn.conf.py`
გაშვებისას უარყოფს.

| ცვლადი | მნიშვნელობა | რა მოხდება, თუ არასწორია |
|---|---|---|
| `APP_ENV` | `production` | **სერვერი არ აიწევს.** დაუყენებლად: `/docs` საჯარო, cookie `Secure`-ის გარეშე, storage მეხსიერებაში |
| `DATABASE_URL` | Supabase-ის pooler-ის URL — group `voltbox-database`-ში | სერვისი ვერ აიწევს |
| `JWT_SECRET` | **ახალი**, ≥32 სიმბოლო | ძველი ტოკენები ძალაში დარჩება |
| `FORWARDED_ALLOW_IPS` | proxy-ის მისამართი | **სერვერი არ აიწევს.** `*`-იც უარყოფილია — მაშინ ნებისმიერს შეუძლია თავისი IP აირჩიოს |
| `TRUSTED_HOSTS` | `api.voltbox.ge` | **სერვერი არ აიწევს** `*`-ზე ან ცარიელზე. API-ს host-ი — storefront-ის დომენი **არა**. `<service>.onrender.com`-ს აპი თვითონ ამატებს. მის გარეშე ყველა მოთხოვნა, health-იც, `400 Invalid host header`-ს აბრუნებს; პასუხი `TRUSTED_HOSTS`-ს არ ახსენებს, ლოგი — ახსენებს. ↓ იხ. TRUSTED_HOSTS |
| `CORS_ORIGINS` | `https://voltbox.ge` | **სერვერი არ აიწევს** ცარიელზე, `*`-ზე, local origin-ზე (`localhost`, `127.0.0.1`, `::1`) ან ელემენტზე, რომელიც origin არ არის (`voltbox.ge` სქემის გარეშე, `https://voltbox.ge/shop` path-ით). სწორი ფორმის, მაგრამ სხვა დომენის origin-ზე აიწევს — და ბრაუზერი მოთხოვნებს დაბლოკავს |
| `SITE_URL` | `https://voltbox.ge` | **სერვერი არ აიწევს** დაუყენებლად (ნაგულისხმევი `http://localhost:5173`-ია), ცარიელზე, `https`-ის გარეშე ან local მისამართზე (`localhost`, `127.x.x.x`, `::1`, `*.localhost`). სწორი ფორმის, მაგრამ სხვა დომენზე აიწევს — sitemap-ის ყველა ბმული, Telegram-ის შეტყობინების ადმინ-ბმული და პაროლის აღდგენის წერილის ბმული იქ მიუთითებს |
| `REDIS_URL` | Redis-ის URL | **სერვერი არ აიწევს**, თუ worker-ი >1. counter-ები worker-ებად გაიყოფა და ლიმიტი გამრავლდება |
| `SUPABASE_PROJECT_REF` | პროექტის ref | სურათების ატვირთვა ჩავარდება (production-ში `RuntimeError`) |
| `SUPABASE_SERVICE_ROLE_KEY` | service role key | იგივე |
| `TELEGRAM_BOT_TOKEN` | @BotFather-ის ტოკენი | არასავალდებულო. ცარიელზე შეტყობინება გამორთულია — შეკვეთა ჩვეულებრივ იქმნება. ↓ იხ. Telegram |
| `TELEGRAM_CHAT_ID` | მფლობელის chat id | იგივე. მხოლოდ ერთი დაყენებული = გამორთული, გაშვებისას WARNING |
| `RESEND_API_KEY` | Resend-ის API key (`re_…`) | არასავალდებულო. ცარიელზე მყიდველს დადასტურება არ ეგზავნება — შეკვეთა ჩვეულებრივ იქმნება — და შესვლის გვერდზე „დაგავიწყდათ პაროლი?" არ ჩანს. ↓ იხ. ელფოსტა |
| `EMAIL_FROM` | `VoltBox <orders@voltbox.ge>` | იგივე. მისამართი Resend-ში დადასტურებულ დომენზე უნდა იყოს, თორემ ყოველი წერილი `HTTP 403`-ით ჩავარდება. მხოლოდ ერთი დაყენებული = გამორთული, გაშვებისას WARNING |
| `WEB_CONCURRENCY` | 2 | ↓ იხ. კავშირებისა და მეხსიერების ბიუჯეტი — ორივეს ამრავლებს |
| `MAX_IMAGE_DECODE_BYTES` | `104857600` (100 MiB) | ერთ სურათის ატვირთვის მეხსიერების ჭერი. ↓ იხ. მეხსიერების ბიუჯეტი |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 5 / 5 | **სერვერი არ აიწევს**, თუ `worker × (pool+overflow)` ბიუჯეტს გადააჭარბებს |
| `DB_SSL_MODE` / `DB_SSL_ROOT_CERT` | გაშვებამდე: `verify-full` / `/etc/secrets/supabase-ca.crt`. `backend/render.yaml`-ში არ წერია, ამიტომ დაუყენებლად მუშაობს `require` | `require` ბაზასთან ტრაფიკს შიფრავს, მაგრამ სერვერს **არ ამოწმებს** — MITM-ისგან არ იცავს; დეპლოიზე გაშვებისას ლოგში WARNING ჩნდება. `verify-full`-ზე: წაუკითხავი ან არა-PEM CA ფაილი — **სერვერი არ აიწევს**; ვალიდური PEM, რომელიც Supabase-ის სერტიფიკატს ან hostname-ს არ ემთხვევა — სერვისი აიწევს (health check `/health/live` ბაზას არ ეხება), მაგრამ ბაზის ყოველი მოთხოვნა ჩავარდება და `/api/v1/health` აჩვენებს `"database": "down"` — სანამ ცვლადები არ დაბრუნდება. ↓ იხ. ბაზასთან TLS |

### ⚠️ TRUSTED_HOSTS — API-ს host-ი, არა storefront-ის

`TRUSTED_HOSTS` API-ზე მოსული მოთხოვნის **`Host`** header-ს ამოწმებს. storefront-იდან
ბრაუზერი აგზავნის `Host: api.voltbox.ge` და `Origin: https://voltbox.ge` —
`Origin`-ი `CORS_ORIGINS`-ის საქმეა. `voltbox.ge`-ზე მოთხოვნები static site-ზე
მიდის და API-ს არასდროს მიაღწევს, ამიტომ storefront-ის დომენს აქ არაფერი აქვს.

გაზომილი: `TRUSTED_HOSTS=voltbox.ge,www.voltbox.ge` → `api.voltbox.ge` →
**400 Invalid host header**.

**Render-ის health check-ი.** HTTP health check-ს Render custom domain-ის
`Host`-ით აგზავნის, *თუ domain-ი verify-ებულია*; მანამდე — service-ის
`onrender.com` hostname-ით. ამ hostname-ს Render service-ს
`RENDER_EXTERNAL_HOSTNAME`-ში აწვდის, და აპი მას `TRUSTED_HOSTS`-ის სიას
**თვითონ უმატებს** — ხელით არსად იწერება. ამიტომ:

1. `TRUSTED_HOSTS=api.voltbox.ge` და Health Check Path —
   **`/api/v1/health/live`** — ორივე `backend/render.yaml`-შია, შექმნისთანავე
   (არა `/api/v1/health` — მიზეზი §9-შია).
2. პირველი deploy-ის შემდეგ:

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://<service>.onrender.com/api/v1/health/live   # 200
   curl -s -o /dev/null -w '%{http_code}\n' https://<service>.onrender.com/api/v1/health        # 200; 503 = ბაზა მიუწვდომელია
   ```

onrender.com-ის hostname-ი Host-ის შემოწმებას **არ ასუსტებს**. ეს Render-ის
host-ია, რომელზეც Render **ეს** service-ი ისედაც გასცემს — custom domain-ის
დამატების შემდეგაც — და სხვაგან მიუთითება შეუძლებელია. სია ჩაკეტილი რჩება:
ნებისმიერი სხვა `Host` ისევ 400-ს აბრუნებს. Render-ის გარეთ ცვლადი არ არსებობს
და სია ზუსტად `TRUSTED_HOSTS`-ია. თუ API onrender.com-ზე საერთოდ არ უნდა ჩანდეს,
ეს ცალკე გადაწყვეტილებაა და Render-ის მხარეს კეთდება — Settings → Custom
Domains → Render Subdomain → Disabled (custom domain-ს ითხოვს).

**როცა `Host`-ი უარყოფილია — სად ჩანს.** `400 Invalid host header`-ის პასუხი
setting-ს არ ასახელებს. აპი ყოველ უარყოფილ მოთხოვნაზე ლოგში ერთ `WARNING`-ს
წერს (§9 — stdout, JSON):

```json
{"ts": "2026-09-19T12:00:00+0000", "level": "WARNING", "logger": "voltbox.hosts", "message": "A request's Host is not in TRUSTED_HOSTS, so it was not served. If every request is refused, the health check included, TRUSTED_HOSTS is missing the name this API is served on."}
```

Render → service → **Logs** → ძებნა `TRUSTED_HOSTS`. თუ health check 400-ს
იღებს, Render deploy-ს 15 წუთში გააუქმებს და ეს ხაზი ყოველ ცდაზე მეორდება: სიას
აკლია სახელი, რომლითაც API-ს მიმართავენ — `api.voltbox.ge`, ან, თუ 400-ს
onrender.com-ის მისამართი აბრუნებს, `RENDER_EXTERNAL_HOSTNAME` არ დაყენდა და
onrender-ის hostname-ი `TRUSTED_HOSTS`-ს ხელით ემატება — `backend/render.yaml`-ში,
არა პანელში, რომელსაც შემდეგი sync-ი გადააწერს. უარყოფილ `Host`-ს ხაზი
**განზრახ არ შეიცავს** — მას გამგზავნი წერს, ხშირად უცხო. სწორი სახელები
dashboard-შია: Settings → Custom Domains. ცალკეული ასეთი ხაზი, როცა დანარჩენი
მოთხოვნები გადის, ჩვეულებრივია — სკანერები უცხო `Host`-ით აკაკუნებენ.

### ⚠️ კავშირების ბიუჯეტი

Supabase-ის `max_connections` = **60**, საიდანაც 3 superuser-ისთვისაა და ~20
Supabase-ის საკუთარ სერვისებს უჭირავს.

```
2 worker × (5 + 5) = 20 კავშირი   ✅
4 worker × (10 + 10) = 80         ❌ სერვერი უარს იტყვის აწევაზე
```

### ⚠️ ბაზასთან TLS — `require`-დან `verify-full`-ზე

ახლა API ბაზას `DB_SSL_MODE=require`-ით უკავშირდება (ნაგულისხმევი; `render.yaml`-ში
არ წერია): ტრაფიკი დაშიფრულია, მაგრამ სერვერის სერტიფიკატი **არ მოწმდება** —
გზაზე ჩადგომილი მხარე თავს Supabase-ად გაასაღებს და ვერ შევამჩნევთ.
Supabase-ის სერტიფიკატს საკუთარი CA აწერს ხელს და ის საჯარო trust store-ში არ
არის, ამიტომ `verify-full`-ს CA-ს ფაილი სჭირდება. დეპლოიზე (`APP_ENV` =
`production`/`staging`) `require`-ზე გაშვებისას ლოგში იწერება WARNING
(logger `voltbox.db`): „encrypted but the server is not authenticated“. ის იწერება
აპის გაშვებისას (lifespan, `configure_logging`-ის შემდეგ: `app/main.py` →
`log_tls_mode`), ყოველ worker-პროცესზე ერთხელ (2 worker — 2 ხაზი), აპის JSON
ლოგერით. `DB_SSL_MODE=disable`-ზე არალოკალურ ბაზასთან დეპლოიზე ცალკე WARNING
იწერება — „The database connection is unencrypted“ (`not authenticated`-ს არ
შეიცავს). შემოწმება ასეა: ლოგში ჩანს ხაზი, რომელიც შეიცავს `not authenticated`-ს
ან `unencrypted`-ს, / `verify-full`-ზე გადასვლის შემდეგ არცერთი აღარ ჩანს. სერვისი ამით არ ჩერდება — გაშვებამდე ის უნდა გაქრეს.

გადართვა (მფლობელის ხელით, Render-ის პანელში; `render.yaml` არ იცვლება):

1. **CA-ს ჩამოტვირთვა:** Supabase Dashboard → Project Settings → Database →
   SSL Configuration → „Download certificate“. ჩამოტვირთული `.crt` ფაილის შიგთავსი
   PEM ტექსტია (`-----BEGIN CERTIFICATE-----`). ფაილი საიდუმლო არ არის, მაგრამ
   repository-შიც არ ვინახავთ.
2. **Render-ზე მიწოდება:** API სერვისი → Environment → **Secret Files** → Add:
   Filename `supabase-ca.crt`, Contents — ფაილის შიგთავსი. Render მას
   `/etc/secrets/supabase-ca.crt`-ზე ამოიტანს.
3. **ცვლადები API სერვისზე** (იგივე Environment, ფაილში არ წერია, ამიტომ
   sync მათ არ გადააწერს):
   - `DB_SSL_MODE=verify-full`
   - `DB_SSL_ROOT_CERT=/etc/secrets/supabase-ca.crt`

   შენახვა ახალ deploy-ს იწყებს.
4. **შემოწმება deploy-ის შემდეგ:**
   - სერვისი აიწია (Events → Deploy live);
   - `curl https://<api-host>/api/v1/health` პასუხში `"database": "up"`;
   - ახალი deploy-ის ლოგში `not authenticated`-ის შემცველი ხაზი აღარ არის.

**თუ ეს არ გამოვა** — ორი სახის ჩავარდნაა: (ა) CA ფაილი წაუკითხავია ან PEM არ არის —
სერვისი არ აიწევს და ლოგში `DB_SSL_ROOT_CERT … cannot be used as a CA bundle`;
(ბ) PEM ვალიდურია, მაგრამ Supabase-ის სერტიფიკატს ან `DATABASE_URL`-ის hostname-ს არ
ემთხვევა — სერვისი **აიწევს** (health check `/api/v1/health/live` ბაზას არ ეხება),
ბაზის ყოველი მოთხოვნა ჩავარდება პირველივე კავშირზე და `/api/v1/health` აბრუნებს
`"database": "down"`. ორივე შემთხვევაში: ორივე ცვლადი წაშალეთ (`DB_SSL_MODE`, `DB_SSL_ROOT_CERT`) —
სისტემა ისევ `require`-ზე დადგება და ძველებურად იმუშავებს — და შედეგი
დააფიქსირეთ. ყველაზე სავარაუდო მიზეზი: `DATABASE_URL`-ის hostname-ს სერტიფიკატი
არ ფარავს. პირდაპირი `db.<ref>.supabase.co` და pooler-ი (`*.pooler.supabase.com`)
სხვადასხვა hostname-ია, და ამ შემოწმებით სწორედ ესაა გასარკვევი — ვარაუდით
არ ვწერთ, ფარავს თუ არა ჩამოტვირთული CA ორივეს. ფაილი არასწორი გზით ან
დაზიანებული PEM-ით სერვერს გაშვებისას აჩერებს და შეცდომა `DB_SSL_ROOT_CERT`-ს
ასახელებს (URL-ს — არასოდეს).

`DB_SSL_ROOT_CERT` დაყენებული `require`-ზეც სრულ ვერიფიკაციას რთავს (ვერიფიკაციის
განზრახვა მდუმარედ არ გამოირთვება), მაგრამ ორივე ცვლადი ერთად სჯობს: მაშინ
კონფიგურაცია თავადვე ამბობს, რომ ვერიფიკაცია ჩართულია.

**ლოკალურად და მიგრაციებისთვის:** `alembic` იმავე `build_connect_args()`-ს
იყენებს, ამიტომ ონლაინ რეჟიმი (`upgrade`, `check`…) იგივე `DB_SSL_*`
ცვლადებით მუშაობს. §5-ის გზა — `alembic upgrade <ძველი>:<ახალი> --sql` —
ბაზას არ უკავშირდება და ამ ცვლილებას არ ეხება. ლოკალური ბაზა (`localhost`,
`127.0.0.1`) TLS-ს არ იყენებს, `DB_SSL_MODE=verify-full`-ის დროსაც.

### ⚠️ მეხსიერების ბიუჯეტი — სურათის ატვირთვა

ატვირთული სურათი 1600px-მდე რომ შემცირდეს, ჯერ მთლიანად უნდა გაიშალოს, და პიკი
სწორედ იქაა. ფასი ფორმატზეა დამოკიდებული — გაზომილი Pillow 12.3-ზე, ამ
Dockerfile-ის იმიჯში — ამიტომ ზღვარი მეხსიერებაშია, პიქსელებში კი მას
`app/services/storage.py` (`DECODE_COST`) გადაიყვანს.

```
ერთი ატვირთვა  ≤ MAX_IMAGE_DECODE_BYTES            100 MiB (ნაგულისხმევი)
პროცესის ჭერი  = WEB_CONCURRENCY × ეს              2 × 100 MiB = 200 MiB
+ worker-ები მოსვენებულ მდგომარეობაში              ≈ 2 × 100 MB
                                                   ≈ 410 MB  →  512 MB-ზე ეტევა
```

ჭერი იმიტომ მუშაობს, რომ გაშლა event loop-ზე სინქრონულად ხდება: ერთი worker-ი
ერთდროულად ერთ სურათს შლის, რამდენი ატვირთვაც არ უნდა მოვიდეს.

**ნაგულისხმევი 512 MB-ის instance-ზეა გათვლილი** (ზომა ჯერ არ არჩეულა). ის
ატარებს ტელეფონის ჩვეულებრივ 12 MP ფოტოს — JPEG 13.3 MP-მდე, PNG 8.3 MP-მდე,
WebP 1.9 MP-მდე — 24 MP-ს კი აღარ. გაზომილი პიკი თითოეულ ამ ზღვარზე, Linux-ზე
და ყველაზე ძვირ ფორმაზე: 90.4 / 90.4 / 90.9 / 91.4 MiB.

**2 GB-ის instance-ზე** (თუ 24 MP-ის ფოტოების ატვირთვა გინდა — iPhone 15–17
ნაგულისხმევად ამას იღებს):

```
MAX_IMAGE_DECODE_BYTES=201326592   # 192 MiB → JPEG 27.1 MP, PNG 19.0 MP, WebP 7.9 MP
```

გაზომილი პიკი ამ ზღვრებზე: 167–182 MiB — ბიუჯეტის 87–95%, ანუ მარაგი უფრო მჭიდროა,
ვიდრე ნაგულისხმევზე (90–91%): ფასის ფიქსირებული ნაწილი ბიუჯეტთან ერთად არ იზრდება.
ჭერი 2 × 192 MiB ≈ 400 MB, worker-ებთან ერთად ≈ 600 MB.

⚠️ `WEB_CONCURRENCY`-ის გაზრდა ამ ჭერს პირდაპირ ამრავლებს — 4 worker-ი
ნაგულისხმევ ზღვარზეც 400 MiB-ია მხოლოდ სურათებისთვის.

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

⚠️ **უფასო plan-ზე job-ი `backend/render.yaml`-ში არ არის.** Render-ს უფასო
cron job-ი არ აქვს (cron-ის plan-ები `0.5c-512mb`-იდან იწყება), და ფასიანი
რესურსი უფასო deploy-ში არ უნდა იყოს. ამ დროს არაფერი ტყდება — `refresh_tokens`
მხოლოდ იზრდება. **ფასიან plan-ზე გადასვლისას job-ი უკან უნდა დაბრუნდეს** —
ზუსტად ის ბლოკი, რაც ამოღებამდე იყო:

```bash
git show cfb7052:backend/render.yaml   # services-ის მეორე ჩანაწერი, type: cron
```

დაბრუნებული job-ი (`voltbox-prune-refresh-tokens`) Blueprint-ის sync-ზე API-სთან
ერთად იქმნება — ხელით არაფერი ემატება:

| ველი | მნიშვნელობა |
|---|---|
| Schedule | `0 23 * * *` — Render-ის cron-ი UTC-ზეა, ეს 03:00 თბილისით |
| Docker Command | `python scripts/prune_refresh_tokens.py` — იგივე Dockerfile, რაც API-ს |
| `DATABASE_URL` | group `voltbox-database`-იდან, იგივე, რაც API-ს (↑ Blueprint-ის შექმნა) |
| `JWT_SECRET` | Render აგენერირებს (`generateValue`) |

group-ი იმისთვისაა, რომ შეცვლილი პაროლი job-ს უკან არ დატოვებს: job-ზე ცალკე
ჩაწერილი `DATABASE_URL` პაროლის შემდეგ rotation-ზე ძველი დარჩებოდა, და job-ი
ყოველ ღამე ჩავარდნდა. `JWT_SECRET` job-ს არ სჭირდება, მაგრამ Settings-ი მის
გარეშე არ აიწევს — ამიტომ მისი მნიშვნელობა შემთხვევითია და API-ს secret-ის
ასლი არ არის. კავშირი ერთია, წამებით, ↑ ბიუჯეტს არ ცვლის.

**რა მოხდება, თუ დამავიწყდება:** არაფერი ტყდება. `refresh_tokens` ყოველ
refresh-ზე ერთ მწკრივით იზრდება — ზღვრის გარეშე, 500 MB-ისკენ. სატესტო deploy-ის
მოკლე ვადაში ეს უმნიშვნელოა; საჭიროების შემთხვევაში ↓ ხელით გაშვება მასვე შლის.

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

### Telegram — შეტყობინება ახალ შეკვეთაზე

ყოველ ახალ შეკვეთაზე მფლობელს Telegram-ზე მოდის: შეკვეთის ნომერი, ჯამი,
ნივთების რაოდენობა და ბმული შეკვეთაზე ადმინ-პანელში (`SITE_URL/admin/orders/<id>`).
მყიდველის სახელი, ტელეფონი და მისამართი **არ** იგზავნება — ისინი ადმინშია.

**ადმინ-პანელი რჩება სიმართლის წყაროდ.** შეტყობინება შეიძლება დაიკარგოს, და
შეკვეთების სია ყოველთვის ადმინში უნდა შემოწმდეს. შეტყობინება იგზავნება
შეკვეთის შენახვის და მყიდველისთვის პასუხის გაცემის **შემდეგ**, ამიტომ Telegram-ის
შეფერხება checkout-ს ვერც ჩააგდებს და ვერც შეანელებს — მაგრამ დაიკარგება, თუ:

- Telegram ~20 წამზე მეტ ხანს მიუწვდომელია (3 ცდა, თითო 5 წამი);
- ტოკენი ან chat id არასწორია, ან მფლობელმა ბოტი დაბლოკა (ხელახლა არ ცდილობს);
- worker-ი პასუხსა და გაგზავნას შორის გადაიტვირთა — მაგ. deploy-ის დროს.

ყოველი ასეთი შემთხვევა ლოგში ERROR-ით ჩნდება:
`Telegram notification for order VB-… was not sent: <მიზეზი>`.

#### ბოტის შექმნა

1. Telegram-ში გახსენით **@BotFather** → `/newbot` → სახელი (მაგ. `VoltBox შეკვეთები`)
   → username, რომელიც `bot`-ით მთავრდება (მაგ. `voltbox_orders_bot`).
2. BotFather გაძლევთ ტოკენს, `123456789:AA…` ფორმის. ეს არის `TELEGRAM_BOT_TOKEN`.
   ვისაც ის აქვს, ბოტის სახელით წერს და ბოტისთვის გაგზავნილს კითხულობს —
   მხოლოდ Render-ის Environment-ში, არც ჩატში, არც repo-ში. გაჟონვისას:
   @BotFather → `/revoke` → ახალი ტოკენი Render-ში.

#### chat id-ის პოვნა

ბოტი პირველი ვერ დაწერს იმას, ვინც მას არ დაუწყია საუბარი — Telegram 403-ს
აბრუნებს. ამიტომ:

1. მფლობელის ანგარიშიდან გახსენით ბოტი (`t.me/<username>`) და დააჭირეთ **Start**.
2. **საკუთარ** ბრაუზერში გახსენით
   `https://api.telegram.org/bot<TOKEN>/getUpdates` — URL-ში ტოკენია, ეკრანის
   სურათს ნუ გააზიარებთ.
3. პასუხში `"chat":{"id":123456789,…}` — ეს რიცხვი არის `TELEGRAM_CHAT_ID`.
   ცარიელი `"result":[]` ნიშნავს, რომ Start ჯერ არ დაჭერილა (ან დიდი ხნის წინ
   იყო — ხელახლა მიწერეთ ბოტს ნებისმიერი რამ და განაახლეთ).

ჯგუფისთვის (რამდენიმე ადამიანი): დაამატეთ ბოტი ჯგუფში, ჯგუფში დაწერეთ
`/start@<username>`, და `getUpdates`-ში ჯგუფის id იქნება — უარყოფითი,
სუპერჯგუფზე `-100`-ით დაწყებული. მთლიანად, მინუსით ჩაწერეთ.

chat id საიდუმლო არ არის: ტოკენის გარეშე მისით ვერაფერს გააგზავნით.

#### შემოწმება

1. გაშვების ლოგში, თითო worker-ზე ერთხელ:
   `Telegram order notifications are on`. თუ `off` წერია, ცვლადი არ იკითხება.
2. საიტზე გააკეთეთ სატესტო შეკვეთა → შეტყობინება წამებში უნდა მოვიდეს, ბმული
   ადმინში იმავე შეკვეთას უნდა ხსნიდეს. შემდეგ შეკვეთა ადმინიდან გააუქმეთ.
3. არ მოვიდა → ლოგში მოძებნეთ `Telegram notification for order`. `HTTP 401` —
   ტოკენი; `HTTP 400: Bad Request: chat not found` — chat id; `HTTP 403` —
   Start არ დაჭერილა ან ბოტი დაბლოკილია.

### ელფოსტა — შეკვეთის დადასტურება მყიდველს

**ამჟამად გამორთულია** — ჩაირთვება, როცა `voltbox.ge` დომენი შეძენილი და
Resend-ში დადასტურებული იქნება. მანამდე ორივე ცვლადი ცარიელია და checkout
ჩვეულებრივ მუშაობს.

ყოველ ახალ შეკვეთაზე მყიდველს მოდის წერილი (HTML და უბრალო ტექსტი, ქართულად):
შეკვეთის ნომერი, პროდუქტები რაოდენობითა და ფასით, მიწოდების საფასური, ჯამი,
მიწოდების მისამართი, გადახდის მეთოდი და მაღაზიის კონტაქტები — იგივე, რაც
საიტის ქვედა ნაწილშია (`frontend/src/constants/index.js`, `CONTACT`; backend-ის
ასლი `app/services/order_email.py`-შია და ტესტი ამოწმებს, რომ ემთხვევა).

ვის: სტუმარს — checkout-ში შეყვანილ ელფოსტაზე (ველი არასავალდებულოა);
შესულ მომხმარებელს — ანგარიშის ელფოსტაზე. ელფოსტის გარეშე შეკვეთაზე წერილი
უბრალოდ არ იგზავნება.

როგორც Telegram-ის შემთხვევაში, წერილი იგზავნება შეკვეთის შენახვისა და
პასუხის **შემდეგ** — Resend-ის შეფერხება checkout-ს ვერც ჩააგდებს და ვერც
შეანელებს. იგივე წესები: 3 ცდა თითო 5 წამით timeout-ზე, კავშირის შეცდომაზე,
429-ზე და 500/502/503/504-ზე;
ერთი ცდა 400/401/403/422-ზე. ყოველი ჩავარდნა ლოგში ERROR-ით:
`Confirmation email for order VB-… was not sent: <მიზეზი>` — მყიდველის
მისამართის გარეშე. ხელახალი ცდა იგივე `Idempotency-Key`-ით მიდის, ამიტომ
timeout-ის შემდეგი ცდა მეორე წერილს არ აგზავნის.

**პაროლის აღდგენაც ამავე ორ ცვლადზეა.** სანამ ისინი ცარიელია, შესვლის გვერდზე
„დაგავიწყდათ პაროლი?" ბმული არ ჩანს და `POST /auth/forgot-password`
`503 PASSWORD_RESET_UNAVAILABLE`-ს აბრუნებს — ბმული, რომელიც არაფერს
აგზავნის, ბმულის არქონაზე უარესია. ჩართვის შემდეგ:

- წერილში ბმულია `SITE_URL`-ზე: `https://voltbox.ge/reset-password#token=…`.
  ტოკენი `#`-ის შემდეგაა — ამ ნაწილს ბრაუზერი სერვერს არ უგზავნის, ამიტომ ის
  არც Render-ის ლოგში ხვდება, არც Referer-ში.
- ბმული მოქმედებს 30 წუთი და ერთხელ; ახალი მოთხოვნა ძველ ბმულს აუქმებს.
  ბაზაში მხოლოდ მისი SHA-256 ინახება (`password_reset_tokens`, ერთი მწკრივი
  ანგარიშზე). წარმატებული აღდგენა ანგარიშის ყველა სესიას ხურავს.
- პასუხი ერთია, მისამართს ანგარიში აქვს თუ არა. ლიმიტი: 5 მოთხოვნა წუთში
  ერთი IP-დან, 3 საათში ერთ მისამართზე (ორივე — Redis-ში, როცა `REDIS_URL`
  დაყენებულია).
- ჩავარდნა ლოგში ERROR-ით: `Password reset email for account <id> was not
  sent: <მიზეზი>` — ანგარიშის id-ით (ადმინში მომხმარებლის მოსაძებნად),
  მისამართისა და ბმულის გარეშე.

#### 1. Resend-ის ანგარიში

1. დარეგისტრირდით <https://resend.com>-ზე (უფასო გეგმა მცირე მაღაზიას
   ჰყოფნის — ლიმიტები Resend-ის Pricing გვერდზე შეამოწმეთ).
2. ანგარიში მაღაზიის ელფოსტაზე გახსენით და არა პირადზე — ვინც ანგარიშს
   მართავს, მაღაზიის სახელით წერს.

#### 2. დომენის დადასტურება (DNS)

Resend მხოლოდ დადასტურებული დომენიდან აგზავნის. დადასტურება ამტკიცებს, რომ
დომენი თქვენია, და მიმღების სერვერს აჩვენებს, რომ წერილი ყალბი არ არის —
მის გარეშე წერილები spam-ში ხვდება ან საერთოდ არ მიდის.

1. Resend → **Domains** → **Add Domain** → `voltbox.ge`. Region — **eu-west-1
   (Ireland)**, საქართველოსთან უახლოესი.
2. Resend აჩვენებს ჩანაწერებს. **მნიშვნელობები ზუსტად იქიდან დააკოპირეთ** —
   DKIM-ის გასაღები ყოველ დომენს თავისი აქვს. ფორმა ასეთია:

   | ტიპი | სახელი (host) | მნიშვნელობა | რისთვის |
   |---|---|---|---|
   | MX | `send` | `feedback-smtp.eu-west-1.amazonses.com`, priority `10` | დაბრუნებული წერილები (bounce) |
   | TXT | `send` | `v=spf1 include:amazonses.com ~all` | SPF — ვის აქვს უფლება, ამ დომენით გააგზავნოს |
   | TXT | `resend._domainkey` | `p=MIGfMA0…` (გრძელი გასაღები) | DKIM — წერილის ხელმოწერა |
   | TXT | `_dmarc` | `v=DMARC1; p=none;` | DMARC — არასავალდებულო, მაგრამ Gmail/Yahoo მას ითხოვს |

3. ჩაწერეთ ისინი დომენის რეგისტრატორის DNS პანელში. host-ის ველში ზოგი
   რეგისტრატორი მხოლოდ `send`-ს ელოდება, ზოგი — `send.voltbox.ge`-ს; თუ
   პანელი დომენს თვითონ ამატებს, მეორეჯერ ნუ ჩაწერთ (`send.voltbox.ge.voltbox.ge`).
   თუ Cloudflare-ია — ჩანაწერები **DNS only** (ნაცრისფერი ღრუბელი).
4. Resend-ში **Verify DNS Records**. სტატუსი `Verified` უნდა გახდეს — ჩვეულებრივ
   წუთებში, DNS-ის გავრცელებას შეიძლება რამდენიმე საათი დასჭირდეს.
   `voltbox.ge`-ზე `_dmarc` ჩანაწერი უკვე თუ არსებობს, მეორეს ნუ დაამატებთ.

`send` ქვედომენზეა მხოლოდ MX და SPF — `voltbox.ge`-ის საკუთარ MX-ს (თუ
მაღაზიას საფოსტო ყუთი აქვს) ეს არ ეხება.

#### 3. გამგზავნი და API key

1. `EMAIL_FROM` — დადასტურებულ დომენზე, სახელითურთ:
   `VoltBox <orders@voltbox.ge>`. ამ მისამართს საფოსტო ყუთი არ სჭირდება
   გასაგზავნად, მაგრამ მყიდველის პასუხი მასზე მივა — თუ ყუთი არ არსებობს,
   პასუხი დაიკარგება. წერილში საკონტაქტო ელფოსტა (`info@voltbox.ge`) ცალკე წერია.
2. Resend → **API Keys** → **Create API Key** → permission **Sending access**,
   domain `voltbox.ge`. გასაღები ერთხელ ჩანს — ეს არის `RESEND_API_KEY`.
   ვისაც ის აქვს, მაღაზიის სახელით წერს — მხოლოდ Render-ის Environment-ში,
   არც ჩატში, არც repo-ში. გაჟონვისას: Resend-ში წაშალეთ და ახალი ჩაწერეთ Render-ში.
3. Render → API სერვისი → Environment → ორივე ცვლადი → შენახვა ახალ deploy-ს იწყებს.

#### შემოწმება

1. გაშვების ლოგში, თითო worker-ზე ერთხელ: `Order confirmation emails are on`.
   თუ `off` წერია, ცვლადი არ იკითხება (WARNING ასახელებს, რომელი).
2. საიტზე სტუმრად გააკეთეთ სატესტო შეკვეთა **საკუთარი** ელფოსტით → წერილი
   წუთში უნდა მოვიდეს (spam-იც შეამოწმეთ). შემდეგ შეკვეთა ადმინიდან გააუქმეთ.
3. არ მოვიდა → ლოგში მოძებნეთ `Confirmation email for order`. `HTTP 401` —
   გასაღები; `HTTP 403` — დომენი ჯერ `Verified` არ არის, ან `EMAIL_FROM`
   სხვა დომენზეა; `HTTP 422` — მისამართის ფორმა. Resend → **Emails** აჩვენებს
   ყოველ გაგზავნილს და მის ბედს (delivered, bounced).
4. შესვლის გვერდზე „დაგავიწყდათ პაროლი?" ახლა ჩანს. მოითხოვეთ ბმული
   **საკუთარი** ანგარიშისთვის → წერილის ბმული უნდა გაიხსნას `SITE_URL`-ზე და
   ახალი პაროლი მიიღოს. არ მოვიდა → ლოგში `Password reset email for account`,
   მიზეზები იგივეა, რაც მე-3 პუნქტში.

---

## 3. Frontend-ის build

ეს **ბილდის დროს** იკითხება, არა გაშვებისას — შეცვლის შემდეგ ხელახლა ბილდი.

`NODE_VERSION` და `VITE_API_MODE` `frontend/render.yaml`-შია. `VITE_API_BASE_URL`-ს
და `VITE_SITE_URL`-ს Render Blueprint-ის შექმნისას **ერთხელ** იკითხავს (§1);
შემდეგ — სერვისის Environment-ის გვერდიდან.

| ცვლადი | მნიშვნელობა | რა მოხდება, თუ არასწორია |
|---|---|---|
| `NODE_VERSION` | `22` | Render საკუთარი ნაგულისხმევით ააწყობს (24.21.0, 2026-09-ის მდგომარეობით) — არა 22-ით, რომლითაც CI ბილდავს და ტესტავს. Render მას `.node-version`-ზე, `.nvmrc`-ზე და `engines`-ზე ადრე კითხულობს, ამიტომ ის წყვეტს |
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
VOLTBOX_NO_DOTENV=1 JWT_SECRET='<ნებისმიერი 32+ სიმბოლო>' DATABASE_URL='postgresql://unused@localhost/unused' \
  alembic upgrade <ძველი>:<ახალი> --sql > migration.sql
# ხელით დაამატეთ public. ყველა ცხრილის სახელს, მერე SQL Editor-ში
```

ონლაინ რეჟიმში `alembic` (ყველა ბრძანება, რომელიც ბაზას უკავშირდება: `upgrade`,
`downgrade`, `stamp`, `check`, `current`) უარს ამბობს არალოკალურ ჰოსტზე, თუ
`VOLTBOX_ALLOW_REMOTE_MIGRATION=1` არ არის დაყენებული. ლოკალურად მხოლოდ
`localhost`, `127.0.0.1` და `::1` ითვლება; URL ჰოსტის გარეშე, ან `host`/`hostaddr`-ით
URL-ის query-ში, არალოკალურია. `--sql` ამას არ ეხება (`backend/alembic/env.py`,
`backend/app/db/local_url.py`).

`backend/.env` ამ repo-ში აღარ არის, ამიტომ `alembic`-ის ყოველ გაშვებას,
რომელიც `backend/alembic/env.py`-ს ასრულებს (`upgrade`, `downgrade`, `stamp`,
`check`, `current` — `--sql`-საც), გარემო თვითონ უნდა მიაწოდოთ. `heads` და
`history` (`-i`-ისა და `current`-ის გარეშე) მხოლოდ `alembic/versions/`-ს
კითხულობენ და `env.py`-ს არ ასრულებენ, ამიტომ მათ ეს ცვლადები არ სჭირდებათ.
`alembic history -i` და `alembic history current:` (ან `:current`) მიმდინარე
რევიზიას ბაზიდან იღებენ და `env.py`-ს უშვებენ — ისინი ონლაინ ბრძანებებივით
იქცევიან, ამიტომ არალოკალურ ჰოსტზე უარს მიიღებენ. `Settings` ორ ცვლადს მოითხოვს —
`DATABASE_URL` და `JWT_SECRET` (მინიმუმ 32 სიმბოლო; migration-ს მისი მნიშვნელობა
არ სჭირდება, ნებისმიერი გრძელი ტექსტი გამოდგება) — და `.env`-ს მუშა საქაღალდიდან
კითხულობს, თუ `VOLTBOX_NO_DOTENV=1` არ არის (`backend/app/core/config.py`).
ამიტომ ორივე ბრძანებაში (ზემოთ და `check`-ისაში) `VOLTBOX_NO_DOTENV=1`,
`JWT_SECRET` და `DATABASE_URL` ერთ ბრძანებაზეა პრეფიქსად. `--sql` ბაზას არ
უკავშირდება, ამიტომ `DATABASE_URL` მისთვის მხოლოდ SQL-ის დიალექტს განსაზღვრავს:
production-ის URL (და პაროლი) აქ არ ჩასვათ, `postgresql://unused@localhost/unused`
საკმარისია.

### `alembic check` production-ზე (მხოლოდ წასაკითხი)

ის ბაზას არ ცვლის, მაგრამ ონლაინ რეჟიმია, ამიტომ override სჭირდება. გაუშვით
**ერთ ბრძანებად, ცვლადი იმავე ხაზზე პრეფიქსად** (Git Bash / Linux):

```bash
cd backend
VOLTBOX_ALLOW_REMOTE_MIGRATION=1 VOLTBOX_NO_DOTENV=1 JWT_SECRET='<ნებისმიერი 32+ სიმბოლო>' DATABASE_URL='<production URL>' alembic check
```

⚠️ **`export VOLTBOX_ALLOW_REMOTE_MIGRATION=1` არასდროს.** დარჩენილი ცვლადი ამ
shell-ის შემდეგ `alembic upgrade`/`downgrade`/`stamp`-საც ხსნის production-ზე —
იმ დაცვას აუქმებს, რისთვისაც ის დაემატა. PowerShell-ს ბრძანებაზე პრეფიქსი არ
აქვს; გამოიყენეთ Git Bash, ან ახალი ფანჯარა, რომელსაც `check`-ის შემდეგ
მაშინვე დახურავთ. `upgrade`/`downgrade`/`stamp` production-ზე ამ გზით არ
გაუშვათ — მიგრაცია ბაზაში მხოლოდ ზემოთა `--sql` გზით, SQL Editor-იდან მიდის.

ნომრები, რომ ეს სექცია არ დაძველდეს, აქ არ ინახება; წაიკითხეთ:

- production-ის რევიზია — SQL Editor-ში: `select version_num from public.alembic_version;`
- კოდის უკანასკნელი რევიზია — `alembic heads` (`backend/`-იდან; ბაზას არ უკავშირდება)

თუ production კოდზე უკან არის, `alembic check` არაფერს შეადარებს და ჩერდება
შეტყობინებით `FAILED: Target database is not up to date.` (ეს ტექსტი კონსოლზე
იბეჭდება; `CommandError` მხოლოდ შიდა exception-ია, რომელსაც CLI ამ ტექსტად
გადააქცევს — `alembic/config.py`, `alembic/autogenerate/api.py`: ბაზის რევიზია
უნდა იყოს კოდის head). ეს ჩავარდნა
არ არის სქემის განსხვავება — ჯერ გაუშვით გადაუსვლელი მიგრაცია `--sql` გზით
(რომელი — `PROGRESS.md`-ის Blockers-ში; 2026-11-15-ზე ეს `0017`-ია), მერე გაიმეორეთ `check`. „სუფთა" პასუხი
სანდოა მხოლოდ მას შემდეგ, რაც ორი ნომერი ერთი გახდება.

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

ჰოსტის საქმეა (Render-ს ავტომატური სერტიფიკატი აქვს). API HSTS-ს
თვითონ აგზავნის, როცა `APP_ENV` = `production` ან `staging`
(`backend/app/core/headers.py`):

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

storefront-იც აგზავნის HSTS-ს (`frontend/render.yaml`), მაგრამ ჯერ მხოლოდ
`Strict-Transport-Security: max-age=300` — `includeSubDomains`-ისა და `preload`-ის
გარეშე, სანამ საიტი onrender.com-ზეა; `voltbox.ge`-ზე გასვლისას იქ მნიშვნელობა
`31536000`-მდე უნდა გაიზარდოს (`frontend/render.yaml`-ის კომენტარი).

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

ორი endpoint, ორი მომხმარებელი:

| Endpoint | ვინ უყურებს | ბაზა გათიშულია |
|---|---|---|
| `/api/v1/health/live` | Render-ის Health Check Path (§2), Dockerfile-ის `HEALTHCHECK` | **200** — ბაზას არ ეხება |
| `/api/v1/health` | uptime-მონიტორი | **503**, body-ში `"database": "down"` |

**uptime-მონიტორი** (UptimeRobot, Better Stack — უფასო, 5 წუთში ეყენება) —
`https://api.voltbox.ge/api/v1/health`, პირობა "HTTP status არ არის 2xx".
შეგატყობინებთ, როცა API მიუწვდომელია **ან** ბაზა გაითიშა — ორივე შემთხვევაში
მაღაზია ვერ ყიდის.

**რატომ არა იგივე endpoint Render-ისთვისაც.** Render ჩავარდნილ health check-ზე
instance-ს რესტარტავს, deploy-ის დროს კი deploy-ს აუქმებს. ბაზის გათიშვას
რესტარტი ვერ შველის: Supabase-ის გათიშვისას instance-ი რესტარტის მარყუჟში
შევიდოდა, ხოლო იმ დროს დაწყებული deploy — სწორი კოდითაც — გაუქმდებოდა. ამიტომ
Render მხოლოდ იმას ამოწმებს, რისი გამოსწორებაც რესტარტს შეუძლია: პროცესი
პასუხობს.

რას ვთმობთ: deploy, რომელიც ბაზას ვერ წვდება (მაგ. არასწორი `DATABASE_URL`),
Render-ისთვის ჯანმრთელია და ტრაფიკს მიიღებს. ამას uptime-მონიტორი
`/api/v1/health`-ის 503-ით იჭერს, deploy-ის შემდეგ კი — §2-ის მეორე `curl`-ი.

ლოგი `stdout`-შია, JSON-ად — Render აგროვებს და ძებნა აქვს. ნედლი კლიენტის IP
ლოგში არსად ჩანს; `voltbox.access`-ში მისი ფსევდონიმია (`client`, §10).

---

## 10. გაშვების შემდეგ — გადამოწმება

```bash
# ღრმა ბმული — თუ ეს 404-ია, rewrite არ მუშაობს
curl -s -o /dev/null -w '%{http_code}\n' https://voltbox.ge/product/<slug>

# storefront-ის header-ები — ღრმა ბმულზე, rewrite-ით გაცემულ პასუხზე
curl -sI https://voltbox.ge/product/<slug> | grep -iE 'content-security|x-frame|x-content-type|referrer-policy|strict-transport'
# strict-transport-security: max-age=300 — ასე უნდა იყოს, სანამ საიტი onrender.com-ზეა (§7);
# voltbox.ge-ზე გასვლის შემდეგ მნიშვნელობა 31536000-მდე იზრდება

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

### rate limit-ის IP — `FORWARDED_ALLOW_IPS`-ის გადამოწმება

ყველა ლიმიტი (შეკვეთა, შესვლა) კლიენტის IP-ზეა მიბმული. თუ
`FORWARDED_ALLOW_IPS` არასწორია, სერვერი ამას არ ამბობს: ყველა მყიდველი Render-ის
proxy-ის IP-ით ჩანს და მთელი მაღაზია ერთ ვედროს იზიარებს (30 შეკვეთა დღეში
ყველასთვის ერთად). ლოგი ნედლ IP-ს არ წერს — `voltbox.access`-ის ყოველ ხაზში
არის `client`: IP-ის 12-სიმბოლოიანი HMAC-ფსევდონიმი (იგივე
`request.client.host`-ისგან, რომელზეც ლიმიტერია მიბმული; `JWT_SECRET`-ის შეცვლა
ყველა მნიშვნელობას ცვლის).

ფსევდონიმიდან IP-ს ვერ ამოიკითხავთ და მცირე ტრაფიკზე შესადარებელი „სხვა
მომხმარებლების ხაზებიც“ არ იქნება, ამიტომ შედარება საკუთარ საჯარო IP-ზე
აიგება: ფსევდონიმი IP-ის ფუნქციაა, ანუ სწორი კონფიგურაციისას **ერთი IP — ერთი
`client`, სხვა IP — სხვა `client`**. ამისთვის საჭიროა ორი ქსელი, რომლებსაც
ნამდვილად სხვადასხვა საჯარო IP აქვთ (მაგ. სახლის Wi-Fi და მობილური ინტერნეტი,
Wi-Fi გამორთული). ყოველ მოთხოვნას თან დაატყვეთ საკუთარი IP იმავე ბრძანებაში
(`api.ipify.org` ამ IP-ს მხოლოდ თქვენს ტერმინალში აჩვენებს, ლოგში ის არ ხვდება);
**ორივე ქსელიდან გაუშვით ორ-ორჯერ**:

```bash
curl -s https://api.ipify.org; echo
curl -s https://api.voltbox.ge/api/v1/health/live
```

ჯერ ipify-ის ოთხი პასუხი შეადარეთ: ერთი ქსელის ორი პასუხი ერთი და იგივე უნდა იყოს
(მობილური ოპერატორის CGNAT-მა IP მოთხოვნებს შორის შეიძლება შეცვალოს — ასეთი წყვილი
გამოტოვეთ და გაიმეორეთ), ორ ქსელს კი სხვადასხვა. თუ ორივე ქსელი ერთსა და იმავე
IP-ს აჩვენებს (VPN, Wi-Fi calling, ერთი ქსელი), ქვემოთ შედარება ვერაფერს
ამტკიცებს — შეცვალეთ ქსელი და ხელახლა დაიწყეთ.

მერე Render-ის Logs-ში იპოვეთ ოთხი `voltbox.access` ხაზი
`"path": "/api/v1/health/live"`-ით (Render-ის საკუთარ health check-ს თავისი
`client` აქვს — გამოტოვეთ) და დაუწყვილეთ ipify-ის პასუხებს დროით:

- **`client` მიჰყვება IP-ს** (ერთი ქსელის ორი ხაზი ერთნაირია, ორი ქსელისა —
  განსხვავებული) — IP სწორად გადადის. ეს ორი მნიშვნელობა არც Render-ის health
  check-ის ხაზებზე უნდა ჩანდეს.
- **`client` არ მიჰყვება IP-ს** — ერთი ქსელის ორი ხაზი განსხვავებულია, ან ორი ქსელი
  ერთნაირია, თუმცა ipify-ის IP-ები განსხვავებულია: `client` Render-ის შიდა proxy-ის
  მისამართის ფსევდონიმია (სხვადასხვა proxy-ინსტანსმა ერთსა და იმავე IP-ზე
  სხვადასხვა მნიშვნელობა შეიძლება მოგცეთ), ანუ `FORWARDED_ALLOW_IPS` არასწორია და
  ყველა კლიენტი ერთ ლიმიტს იზიარებს. შეამოწმეთ API სერვისზე `FORWARDED_ALLOW_IPS`
  env ცვლადი: ის უნდა იყოს Render-ის proxy-ის მისამართი (არა `*`, არა ცარიელი —
  `gunicorn.conf.py` ამ ორს უარყოფს, მაგრამ სხვა არასწორ მნიშვნელობას ვერ
  ხედავს) — იხ. ცხრილი §2.

მერე სრული E2E ცოცხალ დომენზე: `backend/scripts/e2e/journey.py`-ის
მისამართები შეცვალეთ და გაუშვით — ან ხელით გაიარეთ შეკვეთა თავიდან ბოლომდე.

---

## 11. რასაც ავტომატიკა ვერ დაიჭერს

- **რეალურ ტელეფონზე გავლა** — ღილაკები, ფოკუსი, კლავიატურა
- **სკრინრიდერით შემოწმება**
- **პროდუქტის preview გაზიარებისას** — მესამე მხარის crawler-ები JS-ს არ
  უშვებენ, ამიტომ ყველა ბმული მაღაზიის საერთო ბარათს აჩვენებს (§15)
