# Backup და restore

ყველა ბრძანება ამ დოკუმენტში **გაშვებულია და გადამოწმებულია** 2026-09-12-ს
ცოცხალ Supabase-ზე. შედეგი: 13 ცხრილი, 129 სვეტი, 44 ინდექსი, 15 foreign key,
12 check, 9 unique — **0 შეუსაბამობა** ორიგინალთან.

---

## 🔴 ამჟამინდელი მდგომარეობა: ავტომატური backup არ არსებობს

Dashboard-ში გადამოწმებულია 2026-09-12-ს:

> **Free Plan does not include project backups.**
> Upgrade to the Pro Plan for up to 7 days of scheduled backups.

ანუ **არც scheduled backup, არც Point-in-time recovery.** თუ ბაზა დაზიანდა,
შემთხვევით წაიშალა ან პროექტი დაიკარგა — აღსადგენი არაფერია.

ახლა ეს არ არის კრიტიკული: 0 პროდუქტი, 0 შეკვეთა, სქემა კი მიგრაციებშია git-ში.
**გაშვებამდე კი უნდა გადაწყდეს** — შეკვეთა ფულიცაა და დოკუმენტიც.

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

```bash
TARGET='postgresql://voltbox:voltbox@localhost:55433/voltbox_restore'

# 1. სუფთა სქემა + საჭირო გაფართოებები
psql "$TARGET" \
  -c 'drop schema if exists public cascade' \
  -c 'create schema public' \
  -c 'create extension if not exists citext   with schema public' \
  -c 'create extension if not exists pg_trgm  with schema public' \
  -c 'create extension if not exists unaccent with schema public'

# 2. თვითონ restore
psql "$TARGET" -f backups/voltbox-<თარიღი>.sql
```

⚠️ `create schema public` **აუცილებელია**. `with schema public` არსებულ სქემას
ითხოვს — თვითონ არ ქმნის. მის გარეშე restore ჩერდება:
`ERROR: schema "public" does not exist`.

dump-ის საკუთარი `CREATE SCHEMA public` უვნებელ `already exists`-ს დააბრუნებს —
ეს ერთადერთი მოსალოდნელი შეცდომაა. სხვა არა.

### 3. გადამოწმება

restore წარმატებულად ჩათვალე მხოლოდ მაშინ, თუ ეს რიცხვები ემთხვევა:

```sql
select count(*) from information_schema.tables
  where table_schema='public' and table_type='BASE TABLE';   -- 13
select count(*) from pg_indexes where schemaname='public';   -- 44
select version_num from alembic_version;                     -- უნდა ემთხვეოდეს `alembic heads`-ს
select count(*) from users;
select count(*) from products;
select count(*) from orders;
```

---

## 3. ლოკალური Postgres 17-ზე გადაყვანა

`backend/docker-compose.yml` **postgres:16-alpine**-ს უშვებს, production კი
17.6-ია. ორი შედეგი:

1. production-ის backup ლოკალურად **ვერ აღდგება** (იხ. ხაფანგი „ბ")
2. dev და production სხვადასხვა major ვერსიაა — ქცევის სხვაობა ტესტებში არ ჩანს

⚠️ PG16-ის data volume-ს PG17 **ვერ წაიკითხავს**. `voltbox_dev`-ში 61 პროდუქტი
და 6 შეკვეთაა, ამიტომ ჯერ დამპი, მერე გადართვა:

```bash
cd backend

# 1. ლოკალურის დამპი (16-ის pg_dump 16-ის სერვერიდან — ეს მუშაობს)
docker exec voltbox-pg pg_dump -U voltbox --no-owner voltbox_dev > local-dev-backup.sql

# 2. docker-compose.yml: postgres:16-alpine → postgres:17-alpine

# 3. ძველი volume ქრება — ეს ხელახლა შეიქმნება
docker compose down -v
docker compose up -d db

# 4. სქემა და მონაცემები უკან
psql 'postgresql://voltbox:voltbox@localhost:55432/voltbox_dev' -f local-dev-backup.sql
```

ძველი dump ახალ სერვერზე მუშაობს — შებრუნებული მიმართულება (ახლიდან ძველში) არა.
