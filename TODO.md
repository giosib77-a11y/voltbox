# გასაკეთებელი

პრე-დეპლოიმენტის აუდიტი (§0–§25) დასრულებულია — ეს ის არის, რაც დარჩა.
დეტალები: [`docs/deployment.md`](docs/deployment.md) და
[`docs/pre-deployment-checklist.md`](docs/pre-deployment-checklist.md).

---

## 🔴 გაშვებამდე აუცილებელი

- [ ] **1. დომენის არჩევა** — ყველა დანარჩენი მასზეა დამოკიდებული

- [ ] **2. Static site-ი Blueprint-ად**

      Render → New → Blueprint → Blueprint Path: frontend/render.yaml

      SPA-ს და sitemap-ის rewrite-ები და უსაფრთხოების header-ები ფაილშია —
      პანელში ხელით არაფერი ემატება. rewrite-ის გარეშე მთავარი გვერდი
      იმუშავებს და **ყველა გაზიარებული ბმული 404-ს დააბრუნებს** — გაზომილია:
      `/product/<slug>` → 404, `/category/<slug>` → 404, `/admin` → 404.

      CSP-ის img-src-ში Supabase-ის origin-ი ჩაწერილია. connect-src და
      sitemap-ის rewrite სატესტოდ voltbox-api.onrender.com-ზეა — დომენის
      შემდეგ უკან api.voltbox.ge-ზე: grep -rn TEMP-ONRENDER (deployment.md §0).

      grep -v '^\s*#' frontend/render.yaml | grep -oE '<[A-Z_]+>'   ← ცარიელი უნდა იყოს

- [ ] **3. Frontend-ის ბილდის ცვლადები** (ბილდის დროს იკითხება!)

      VITE_API_MODE=http                      ← frontend/render.yaml-შია. ამის
                                                 გარეშე მაღაზია 61 სატესტო პროდუქტს
                                                 აჩვენებს მეხსიერებიდან და შეკვეთა
                                                 არსად წავა
      VITE_API_BASE_URL=https://<api>/api/v1  ← ეს ორი Blueprint-ის შექმნისას
      VITE_SITE_URL=https://<დომენი>             ერთხელ იკითხება

- [ ] **4. Backend-ი Blueprint-ად** (deployment.md §2)

      Render → New → Blueprint → Blueprint Path: backend/render.yaml

      API (plan: free — სატესტოდ, deployment.md §0), Health Check Path
      (/api/v1/health/live), APP_ENV, TRUSTED_HOSTS, CORS_ORIGINS და SITE_URL
      ფაილშია. ⚠️ refresh-ტოკენების cron job-ი უფასოზე ამოღებულია — ფასიანზე
      გადასვლისას plan 0.5c-512mb-ზე და job-ი უკან (deployment.md §2, Cron job).

      შექმნისას ერთხელ იკითხება:
      JWT_SECRET=<ახალი>            ← python -c "import secrets; print(secrets.token_urlsafe(48))"
      FORWARDED_ALLOW_IPS=<proxy-ს მისამართი>
      REDIS_URL=<redis>             ← საჭიროა, თუ worker-ი 1-ზე მეტია
      SUPABASE_PROJECT_REF, SUPABASE_SERVICE_ROLE_KEY

      შემდეგ: Environment Groups → voltbox-database → DATABASE_URL.
      მანამდე API-ს პირველი deploy ჩავარდება — ეს მოსალოდნელია.

      კავშირების ბიუჯეტი: `worker × (DB_POOL_SIZE + DB_MAX_OVERFLOW) ≤ 30`.
      Supabase-ს 60 აქვს, საიდანაც ~23 უკვე დაკავებულია.

---

## 🟡 გაშვებამდე გადასაწყვეტი

- [ ] **5. Backup** — Supabase Free Plan-ს არც scheduled backup აქვს, არც PITR.

      A. Supabase Pro — $25/თვე, დღიური backup 7 დღე  ← რეკომენდაცია
      C. ხელით dump რისკიან ოპერაციამდე — უფასო, მაგრამ გახსენებაზეა დამოკიდებული

      ბაზაში უკვე დევს ხელით შეყვანილი სამუშაო (ადმინი, კატეგორიები, ბრენდები,
      პროდუქტი), რომელიც მიგრაციებში არაა.
      პროცედურა: [`docs/backup-restore.md`](docs/backup-restore.md)

- [ ] **6. Uptime-შემოწმება** — `/api/v1/health` მზადაა, მაგრამ მას არავინ
      ეკითხება. UptimeRobot ან Better Stack — უფასო, 5 წუთი.

- [ ] **7. robots.txt-ის ბოლო ხაზი** — დომენი ჩასვით და გაუკომენტარეთ:

      Sitemap: https://<api>/sitemap.xml

- [ ] **8. `/sitemap.xml` → API-ზე rewrite** — `frontend/render.yaml`-შია, `/*`-ის
      ზემოთ (crawler-ს ერთი დომენი ურჩევნია). deploy-ის შემდეგ:
      `curl -s https://<დომენი>/sitemap.xml` XML-ს უნდა აბრუნებდეს, არა index.html-ს

- [ ] **9. Google Search Console** — დომენის დადასტურება და sitemap-ის გაგზავნა

- [ ] **10. Repo საჯაროა**

      ხილვადობა: ცოცხალი მაღაზიის კოდი საჯაროდ ნიშნავს, რომ ვალიდაციის
                 წესები, rate limit-ები, ადმინის endpoint-ები და სქემა
                 ღიად ჩანს. ეს თავისთავად დაუცველობა არაა — კოდი კარგადაა
                 დაწერილი — მაგრამ თავდამსხმელს რუკას აძლევს.
                 **რეკომენდაცია: private.**

      About:     description და topics ცარიელია (react, fastapi, postgresql,
                 ecommerce, georgian)

---

## 🟢 გაშვების შემდეგ ან როცა მოგინდებათ

- [x] **11. ლოკალური Postgres 16 → 17** — **გაკეთდა.** `docker-compose.yml`
      17-ზეა, როგორც CI და production. 16-ის დროს შექმნილ volume-ს ხელახლა
      შექმნა სჭირდება — პროცედურა: `docs/backup-restore.md` §3

- [ ] **12. ჩაბარებაზე უარის სტატუსი** — `shipped`-იდან ერთადერთი გზა
      `delivered`-ია. თუ კურიერს უარს ეტყვიან (ნაღდი ანგარიშსწორებისას ხშირია),
      ან ტყუილი უნდა მოინიშნოს, ან შეკვეთა სამუდამოდ „გზაში" დარჩება.
      შემოვლითი გზა არსებობს: მარაგში ხელით დამატება მიზეზით `return`.

- [ ] **13. Audit log-ის ეკრანი პანელში** — 17 სახის ქმედება იწერება, მაგრამ
      წაკითხვა მხოლოდ SQL-ით შეიძლება

- [ ] **14. პროდუქტის preview გაზიარებისას** — Facebook და Messenger JS-ს არ
      უშვებენ, ამიტომ ყველა ბმული მაღაზიის საერთო ბარათს აჩვენებს.
      კონკრეტული პროდუქტის ფოტო და ფასი SSR-ს ან prerender-ს ითხოვს.

- [ ] **15. `srcset`** — რამდენიმე ზომის სურათი. ახლა 1600px-ის ჭერია.

- [ ] **16. `utils/search.js`-ის ტესტები** — 0% დაფარვა (225 ხაზი).
      შედეგები backend-ს შედარებულია (261 სახელი, 0 სხვაობა), ტესტი არაა.

- [ ] **17. ტაბებზე ისრებით ნავიგაცია** — ARIA-ს ნიმუში ისრებს ელოდება.
      Tab-ით სრულად მუშაობს.

- [ ] **18. სრული e2e CI-ში** — docker + ბაზა + ორი სერვერი სჭირდება.
      ახლა ხელით: `backend/scripts/e2e/up.sh` და `journey.py`

---

## ✋ რასაც ავტომატიკა ვერ დაიჭერს

- [ ] **რეალურ ტელეფონზე გავლა** — ღილაკები, ფოკუსი, მობილური კლავიატურა
- [ ] **სკრინრიდერით შემოწმება**
- [ ] **ცოცხალ დომენზე სრული შეკვეთა** — გაშვების პირველი საქმე

---

## გაშვების შემდეგ — შესამოწმებელი

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://<დომენი>/product/<slug>   # 200, არა 404
curl -s https://<api>/api/v1/health
curl -s -o /dev/null -w '%{http_code}\n' https://<api>/docs                # 404
curl -sI https://<api>/api/v1/health | grep -i strict-transport
curl -s https://<api>/sitemap.xml | grep -c '<loc>'
curl -s https://<დომენი> | grep 'og:image'
```
