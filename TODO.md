# გასაკეთებელი

პრე-დეპლოიმენტის აუდიტი (§0–§25) დასრულებულია — ეს ის არის, რაც დარჩა.
დეტალები: [`docs/deployment.md`](docs/deployment.md) და
[`docs/pre-deployment-checklist.md`](docs/pre-deployment-checklist.md).

---

## 🔴 გაშვებამდე აუცილებელი

- [ ] **1. დომენის არჩევა** — ყველა დანარჩენი მასზეა დამოკიდებული

- [ ] **2. SPA rewrite ჰოსტის პანელში**

      Source: /*        Destination: /index.html        Action: Rewrite

      ⚠️ `Rewrite`, არა `Redirect`. ამის გარეშე მთავარი გვერდი იმუშავებს და
      **ყველა გაზიარებული ბმული 404-ს დააბრუნებს** — გაზომილია:
      `/product/<slug>` → 404, `/category/<slug>` → 404, `/admin` → 404.

- [ ] **3. Frontend-ის ბილდის ცვლადები** (ბილდის დროს იკითხება!)

      VITE_API_MODE=http                      ← ამის გარეშე მაღაზია 61 სატესტო
                                                 პროდუქტს აჩვენებს მეხსიერებიდან
                                                 და შეკვეთა არსად წავა
      VITE_API_BASE_URL=https://<api>/api/v1
      VITE_SITE_URL=https://<დომენი>

- [ ] **4. Backend-ის ცვლადები**

      APP_ENV=production            ← დაუყენებლად სერვერი არ აიწევს
      JWT_SECRET=<ახალი>            ← python -c "import secrets; print(secrets.token_urlsafe(48))"
      TRUSTED_HOSTS=<დომენი>,www.<დომენი>
      CORS_ORIGINS=https://<დომენი>
      SITE_URL=https://<დომენი>
      FORWARDED_ALLOW_IPS=<proxy-ს მისამართი>
      REDIS_URL=<redis>             ← საჭიროა, თუ worker-ი 1-ზე მეტია
      SUPABASE_PROJECT_REF, SUPABASE_SERVICE_ROLE_KEY

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

- [ ] **8. `/sitemap.xml` → API-ზე rewrite** ჰოსტის პანელში (crawler-ს ერთი
      დომენი ურჩევნია)

- [ ] **9. Google Search Console** — დომენის დადასტურება და sitemap-ის გაგზავნა

---

## 🟢 გაშვების შემდეგ ან როცა მოგინდებათ

- [ ] **10. ლოკალური Postgres 16 → 17** — CI და production უკვე 17-ია.
      კონტეინერის volume-ის ხელახლა შექმნას ითხოვს; `voltbox_dev`-ში 61
      პროდუქტი და 6 შეკვეთაა. პროცედურა: `docs/backup-restore.md` §3

- [ ] **11. ჩაბარებაზე უარის სტატუსი** — `shipped`-იდან ერთადერთი გზა
      `delivered`-ია. თუ კურიერს უარს ეტყვიან (ნაღდი ანგარიშსწორებისას ხშირია),
      ან ტყუილი უნდა მოინიშნოს, ან შეკვეთა სამუდამოდ „გზაში" დარჩება.
      შემოვლითი გზა არსებობს: მარაგში ხელით დამატება მიზეზით `return`.

- [ ] **12. Audit log-ის ეკრანი პანელში** — 17 სახის ქმედება იწერება, მაგრამ
      წაკითხვა მხოლოდ SQL-ით შეიძლება

- [ ] **13. პროდუქტის preview გაზიარებისას** — Facebook და Messenger JS-ს არ
      უშვებენ, ამიტომ ყველა ბმული მაღაზიის საერთო ბარათს აჩვენებს.
      კონკრეტული პროდუქტის ფოტო და ფასი SSR-ს ან prerender-ს ითხოვს.

- [ ] **14. `srcset`** — რამდენიმე ზომის სურათი. ახლა 1600px-ის ჭერია.

- [ ] **15. `utils/search.js`-ის ტესტები** — 0% დაფარვა (225 ხაზი).
      შედეგები backend-ს შედარებულია (261 სახელი, 0 სხვაობა), ტესტი არაა.

- [ ] **16. ტაბებზე ისრებით ნავიგაცია** — ARIA-ს ნიმუში ისრებს ელოდება.
      Tab-ით სრულად მუშაობს.

- [ ] **17. სრული e2e CI-ში** — docker + ბაზა + ორი სერვერი სჭირდება.
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
