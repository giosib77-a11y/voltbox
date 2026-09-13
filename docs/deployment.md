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

**Render Static Site → Redirects/Rewrites:**

| Source | Destination | Action |
|---|---|---|
| `/*` | `/index.html` | **Rewrite** |

⚠️ `Redirect` **არა** — `Rewrite`. Redirect მისამართს შეცვლის და ბმული
დაიკარგება.

---

## 2. Backend-ის environment

| ცვლადი | მნიშვნელობა | რა მოხდება, თუ არასწორია |
|---|---|---|
| `APP_ENV` | `production` | **სერვერი არ აიწევს.** დაუყენებლად: `/docs` საჯარო, cookie `Secure`-ის გარეშე, storage მეხსიერებაში |
| `DATABASE_URL` | Supabase-ის pooler-ის URL | სერვისი ვერ აიწევს |
| `JWT_SECRET` | **ახალი**, ≥32 სიმბოლო | ძველი ტოკენები ძალაში დარჩება |
| `FORWARDED_ALLOW_IPS` | proxy-ის მისამართი | **სერვერი არ აიწევს.** `*`-იც უარყოფილია — მაშინ ნებისმიერს შეუძლია თავისი IP აირჩიოს |
| `TRUSTED_HOSTS` | `voltbox.ge,www.voltbox.ge` | **სერვერი არ აიწევს** `*`-ზე ან ცარიელზე |
| `CORS_ORIGINS` | `https://voltbox.ge` | ბრაუზერი მოთხოვნებს დაბლოკავს |
| `SITE_URL` | `https://voltbox.ge` | sitemap-ის ბმულები არასწორ დომენზე მიუთითებს |
| `REDIS_URL` | Redis-ის URL | **სერვერი არ აიწევს**, თუ worker-ი >1. counter-ები worker-ებად გაიყოფა და ლიმიტი გამრავლდება |
| `SUPABASE_PROJECT_REF` | პროექტის ref | სურათების ატვირთვა ჩავარდება (production-ში `RuntimeError`) |
| `SUPABASE_SERVICE_ROLE_KEY` | service role key | იგივე |
| `WEB_CONCURRENCY` | 2 | ↓ იხ. კავშირების ბიუჯეტი |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 5 / 5 | **სერვერი არ აიწევს**, თუ `worker × (pool+overflow)` ბიუჯეტს გადააჭარბებს |

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

---

## 3. Frontend-ის build

ეს **ბილდის დროს** იკითხება, არა გაშვებისას — შეცვლის შემდეგ ხელახლა ბილდი.

| ცვლადი | მნიშვნელობა | რა მოხდება, თუ არასწორია |
|---|---|---|
| `VITE_API_MODE` | `http` | **მაღაზია 61 სატესტო პროდუქტს აჩვენებს** მეხსიერებიდან და შეკვეთა არსად წავა |
| `VITE_API_BASE_URL` | `https://api.voltbox.ge/api/v1` | ვერცერთი მოთხოვნა ვერ გავა |
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
ერთი დომენი ურჩევნია, ამიტომ სტატიკურ ჰოსტზე დაამატეთ:

| Source | Destination | Action |
|---|---|---|
| `/sitemap.xml` | `https://api.voltbox.ge/sitemap.xml` | Rewrite |

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

ამჟამად ბაზა `0010`-ზეა და `alembic check` სუფთაა.

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

ლოგი `stdout`-შია, JSON-ად — Render აგროვებს და ძებნა აქვს.

---

## 10. გაშვების შემდეგ — გადამოწმება

```bash
# ღრმა ბმული — თუ ეს 404-ია, rewrite არ მუშაობს
curl -s -o /dev/null -w '%{http_code}\n' https://voltbox.ge/product/<slug>

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
