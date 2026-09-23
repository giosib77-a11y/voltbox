# Backup და restore

Restore-ის ყველა ბრძანება (ნაწილი 2, გადამოწმების ჩათვლით) **გაშვებულია და
გადამოწმებულია** ზუსტად ისე, როგორც აქ წერია. ბოლო სავარჯიშო: **2026-09-23**,
მიგრაცია `0011`, ლოკალურ Docker-ზე.

```
14 ცხრილი · 136 სვეტი · 48 ინდექსი · 53 შეზღუდვა · 1 sequence
ყველა ცხრილის მწკრივების რაოდენობა ემთხვევა
→ 0 ნამდვილი შეუსაბამობა
```

**რა არ გაეშვა ამ სავარჯიშოზე** — production-ს სავარჯიშო არ ეხება:

- **Backup-ის ბრძანება (ნაწილი 1) Supabase-ზე.** dump აღებულია ლოკალური
  `voltbox_dev`-იდან, იმავე `pg_dump`-ის ფლაგებით (იხ. „სავარჯიშო" ქვემოთ).
  Supabase-იდან ბოლოს 2026-09-13-ს, მიგრაცია `0010`-ზე აიღეს.
- **გადამოწმება ცოცხალ ბაზასთან.** ნაგულისხმევად სკრიპტი `.env`-ის
  `DATABASE_URL`-ს (ანუ Supabase-ს) ადარებს; სავარჯიშოზე `--against`-ით
  `voltbox_dev`-ს შეედარა.

⚠️ ციფრები სქემასთან ერთად იცვლება. **ხელით ნუ შეადარებთ** —
`scripts/verify_restore.py` ორივე ბაზას ერთმანეთს ადარებს (ნაწილი 2, „გადამოწმება").

---

## 🔴 ამჟამინდელი მდგომარეობა: ავტომატური backup არ არსებობს

Dashboard-ში გადამოწმებულია 2026-09-12-ს:

> **Free Plan does not include project backups.**
> Upgrade to the Pro Plan for up to 7 days of scheduled backups.

ანუ **არც scheduled backup, არც Point-in-time recovery.** თუ ბაზა დაზიანდა,
შემთხვევით წაიშალა ან პროექტი დაიკარგა — აღსადგენი არაფერია.

**ეს უკვე აღარ არის თეორიული.** 2026-09-13-ის მდგომარეობით ბაზაში უკვე დევს
ადმინის ანგარიში, 6 კატეგორია, 10 ბრენდი და პანელით შეყვანილი პროდუქტი — ანუ
ხელით გაკეთებული სამუშაო, რომელიც მიგრაციებში არაა და დაკარგვის შემთხვევაში
თავიდან უნდა აიკრიფოს. შეკვეთების დამატებისთანავე კი ფულიც და დოკუმენტიც
დაემატება.

### სამი გზა

| | რა | ფასი | ვისთვის |
|---|---|---|---|
| **A** | Supabase **Pro** — დღიური backup, 7 დღე | $25/თვე | გაშვებული მაღაზია. ყველაზე მარტივი და საიმედო |
| **B** | ავტომატური `pg_dump` GitHub Actions-ით | უფასო | ⚠️ პროდაქშენის მონაცემები (სახელები, ტელეფონები, მისამართები) GitHub-ის artifact-ებში მოხვდება, და ბაზის პაროლი secrets-ში. მომხმარებლების მონაცემებისთვის ეს კარგი ადგილი არაა |
| **C** | ხელით dump (ქვემოთ) რისკიან ოპერაციამდე | უფასო | **ახლანდელი ეტაპისთვის საკმარისი** |

**რეკომენდაცია:** ახლა — **C**. გაშვებამდე — **A**.

`B` მხოლოდ მაშინ, თუ Pro არ განიხილება; მაშინაც dump დაშიფრული უნდა იყოს და
artifact-ის retention მოკლე.

---

## 1. Backup

ერთი ბრძანება. URL-ს თვითონ კითხულობს `.env`-იდან, ანუ პაროლი არსად იწერება:

```bash
cd backend
URL=$(grep -E '^DATABASE_URL=' .env | cut -d= -f2-)
docker run --rm postgres:17-alpine \
  pg_dump --schema=public --no-owner --no-acl --format=plain "$URL" \
  > "backups/voltbox-$(date +%Y%m%d-%H%M).sql"
```

`backend/backups/` თავის `.gitignore`-ს ატარებს, ამიტომ იქ დადებული ფაილი
git-ში ვერ მოხვდება.

**`postgres:17-alpine` სავალდებულოა.** Supabase-ზე სერვერი 17.6-ია, `pg_dump`-ის
16 კი უფრო ახალი სერვერიდან dump-ს **უარს ამბობს**.

⚠️ ფაილი შეიცავს ყველა მომხმარებლის მონაცემს — სახელებს, ტელეფონებს,
მისამართებს. `backend/backups/`-ის გარეთ თუ გაიტან, ეს გახსოვდეს.

---

## 2. Restore

### ⚠️ ორი ხაფანგი, რომელშიც ეს dump გვამწყვდევს

**ა) გაფართოებები dump-ში არ არის.** `pg_dump --schema=public` **ვერცერთ**
`CREATE EXTENSION`-ს არ წერს, სქემას კი სამი სჭირდება:

| გაფართოება | რისთვის |
|---|---|
| `citext` | `users.email` — რეგისტრზე დამოუკიდებელი ტიპი |
| `pg_trgm` | ძებნის GIN ინდექსები (`name`, `search_text`) |
| `unaccent` | `search_text`-ის ნორმალიზება |

მათ გარეშე restore ჩერდება:
`ERROR: type "public.citext" does not exist`

**ბ) სამიზნე Postgres 17 უნდა იყოს.** PG16-ში იგივე ფაილი ჩერდება:
`ERROR: unrecognized configuration parameter "transaction_timeout"`
(ეს პარამეტრი PG17-შია შემოტანილი).

### გადამოწმებული პროცედურა

სამიზნე **ცალკე, ერთჯერადი PG17 სერვერია** :55433-ზე — არა compose-ის
`voltbox-pg` (:55432), რომ dev-ის ბაზას არაფერი მოუვიდეს. `psql` host-ზე
საჭირო არაა: ის სამიზნე კონტეინერის შიგნით ეშვება.

```bash
cd backend

# 0. სამიზნე: PG17 სერვერი :55433-ზე, ცარიელი voltbox_restore ბაზით.
#    -h 127.0.0.1: init-ის დროებითი სერვერი მხოლოდ socket-ს უსმენს,
#    ამიტომ ეს ციკლი მხოლოდ ნამდვილ სერვერზე ჩერდება
docker run -d --name voltbox-restore \
  -e POSTGRES_USER=voltbox -e POSTGRES_PASSWORD=voltbox -e POSTGRES_DB=voltbox_restore \
  -p 55433:5432 postgres:17-alpine
until docker exec voltbox-restore pg_isready -q -h 127.0.0.1 -U voltbox -d voltbox_restore; do sleep 1; done

PSQL='docker exec -i voltbox-restore psql -U voltbox -d voltbox_restore'

# 1. სუფთა სქემა + საჭირო გაფართოებები
$PSQL \
  -c 'drop schema if exists public cascade' \
  -c 'create schema public' \
  -c 'create extension if not exists citext   with schema public' \
  -c 'create extension if not exists pg_trgm  with schema public' \
  -c 'create extension if not exists unaccent with schema public'

# 2. თვითონ restore. ON_ERROR_STOP აქ არ გვინდა — იხ. ქვემოთ
$PSQL -q < backups/voltbox-<თარიღი>.sql
```

⚠️ `create schema public` **აუცილებელია**. `with schema public` არსებულ სქემას
ითხოვს — თვითონ არ ქმნის. მის გარეშე restore ჩერდება:
`ERROR: schema "public" does not exist`.

dump-ის საკუთარი `CREATE SCHEMA public` უვნებელ `already exists`-ს დააბრუნებს —
ეს ერთადერთი მოსალოდნელი შეცდომაა. სხვა არა. სწორედ ამიტომ ნაბიჯ 2-ს
`ON_ERROR_STOP` არ აქვს: ამ შეცდომაზე restore თავიდანვე გაჩერდებოდა.

### 3. გადამოწმება

**არ დაეყრდნოთ თვალით შემოწმებას.** ერთი დაკარგული ინდექსი ან check
შეუმჩნეველი რჩება მანამ, სანამ არ დასჭირდება. იმავე `backend/`-იდან:

```bash
python scripts/verify_restore.py postgresql://voltbox:voltbox@localhost:55433/voltbox_restore

# ბოლოს სამიზნე ქრება
docker rm -f voltbox-restore
```

სკრიპტი ორივე ბაზიდან კითხულობს ცხრილებს, სვეტებს (ტიპითა და default-ით),
ინდექსებს, შეზღუდვებს, sequence-ებს და თითოეული ცხრილის მწკრივების რაოდენობას.

აღდგენა წარმატებულია მხოლოდ მაშინ, როცა:

```
real mismatches : 0
```

#### ⚠️ „cosmetic" განსხვავებები ნორმალურია

check-შეზღუდვების ტექსტს სერვერი და `pg_dump` სხვადასხვაგვარად წერენ:

```
სერვერი  :  ANY ((ARRAY['pending'::character varying, ...])::text[])
dump-ის შემდეგ:  ANY (ARRAY[('pending'::character varying)::text, ...])
```

ეს **ერთი და იგივე შეზღუდვაა** — მხოლოდ cast-ის ადგილია სხვა. სკრიპტი მათ
`cosmetic`-ად ითვლის და ცალკე აჩვენებს. 2026-09-13-ის სავარჯიშოზე 6 ასეთი იყო
(3 შეზღუდვა × 2 მხარე), და აღდგენილ ბაზაზე ქცევითაც შემოწმდა: უცნობი სტატუსი,
უცნობი გადახდის მეთოდი და უცნობი მარაგის მიზეზი — სამივე უარყოფილი.

### სავარჯიშო (production-ის გარეშე)

იგივე პროცედურა, მხოლოდ dump ლოკალური `voltbox_dev`-იდან და შედარება მასთან.
`voltbox-pg` (compose-ის `db`) გაშვებული უნდა იყოს:

```bash
cd backend
docker exec voltbox-pg pg_dump -U voltbox --schema=public --no-owner --no-acl --format=plain voltbox_dev \
  > backups/voltbox-rehearsal.sql

# ნაწილი 2-ის ნაბიჯები 0–2, ფაილით backups/voltbox-rehearsal.sql, შემდეგ:
python scripts/verify_restore.py postgresql://voltbox:voltbox@localhost:55433/voltbox_restore \
  --against postgresql://voltbox:voltbox@localhost:55432/voltbox_dev
docker rm -f voltbox-restore
```

2026-09-23-ს (მიგრაცია `0011`) შედეგი: ექვსივე კატეგორია `OK`,
`real mismatches : 0`, exit `0`; restore-ის ერთადერთი შეცდომა — `schema "public"
already exists`. `cosmetic` აქ 0 იყო და არა 6: `voltbox_dev` თვითონ dump-იდანაა
აღდგენილი (ნაწილი 3, PG17-ზე გადაყვანა), ამიტომ მისი check-ები უკვე dump-ის ფორმით წერია.

---

## 3. ლოკალური Postgres 17-ზე გადაყვანა

`backend/docker-compose.yml` **postgres:17-alpine**-ს უშვებს — იმავე major
ვერსიას, რაზეც CI და production (17.6) დგას. 16-ზე ყოფნისას production-ის backup
ლოკალურად ვერ აღდგებოდა (ხაფანგი „ბ"), და dev-ისა და production-ის ქცევის
სხვაობა ლოკალურ ტესტებში არ ჩანდა.

⚠️ **16-ის დროს შექმნილი volume ხელახლა უნდა შეიქმნას.** PG17 მას ვერ კითხულობს
და კონტეინერი არ აიწევს:

```
FATAL:  database files are incompatible with server
DETAIL:  The data directory was initialized by PostgreSQL version 16, which is not compatible with this version 17.11.
```

მონაცემი ამით ჯერ არ იკარგება — იკარგება `down -v`-ით. `voltbox_dev`-ში 61
პროდუქტი და 6 შეკვეთაა, ამიტომ ჯერ დამპი, სანამ ძველი კონტეინერი ისევ 16-ზე
დგას — ანუ ამ ცვლილების `pull`-ის შემდეგ, `docker compose up`-მდე. თუ `up` უკვე
გაეშვა და ზემოთა შეცდომა გამოჩნდა, `image` დროებით `postgres:16-alpine`-ზე
დააბრუნეთ, `docker compose up -d db`, და მხოლოდ მერე ნაბიჯი 1.

```bash
cd backend

# 1. დამპი ძველი, 16-ის კონტეინერიდან. backups/ git-ში არ მიდის
docker exec voltbox-pg pg_dump -U voltbox --no-owner voltbox_dev > backups/local-dev-backup.sql

# 2. volume ქრება და 17-ით თავიდან იქმნება. down Redis-საც აჩერებს
docker compose down -v
docker compose up -d --wait db redis

# 3. ახალ volume-ში მხოლოდ `voltbox` ბაზაა. voltbox_test ტესტებს სჭირდებათ —
#    სქემას თავად აწყობენ მიგრაციებით, ბაზას კი არა
docker exec voltbox-pg createdb -U voltbox voltbox_dev
docker exec voltbox-pg createdb -U voltbox voltbox_test

# 4. სქემა და მონაცემები უკან. ON_ERROR_STOP — რომ შეცდომა არ ჩაიკარგოს
docker exec -i voltbox-pg psql -U voltbox -d voltbox_dev -q -v ON_ERROR_STOP=1 < backups/local-dev-backup.sql
```

2026-09-19-ს ასე გადავიდა: `voltbox_dev` (61 პროდუქტი, 6 შეკვეთა, მიგრაცია
`0011`) შეცდომის გარეშე აღდგა, pytest-ის შედეგი 16-ზე და 17.11-ზე იდენტურია, და
მიგრაციებით აწყობილი სქემის `pg_dump --schema-only` ორივეზე ერთნაირია — სერვერის
ვერსიის ხაზის გარდა.

ძველი dump ახალ სერვერზე მუშაობს — შებრუნებული მიმართულება (ახლიდან ძველში) არა.
