# VoltBox Backend

FastAPI + PostgreSQL REST API for the VoltBox store. Replaces the frontend's mock
data layer without any component changes — only `VITE_API_MODE=http`.

> monorepo-ს ნაწილი. ზოგადი მიმოხილვა — [`../README.md`](../README.md),
> კლიენტის მხარე — [`../frontend/README.md`](../frontend/README.md).
> ყველა ქვემოთ მოცემული ბრძანება `backend/`-იდან სრულდება.

## Quick start

```bash
# 1. ბაზა და Redis (ტესტებსაც სჭირდებათ)
docker compose up -d --wait db redis
# ტესტების ბაზა, ერთხელ: compose მხოლოდ `voltbox`-ს ქმნის, conftest.py კი
# `voltbox_test`-ს უკავშირდება და ყოველ გაშვებაზე მასში სქემას თავიდან აწყობს
docker compose exec db createdb -U voltbox voltbox_test

# 2. გარემო
cp .env.example .env        # DATABASE_URL და JWT_SECRET შეავსე

# 3. დამოკიდებულებები
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"     # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # Linux / macOS

# 4. მიგრაციები და საწყისი მონაცემები
alembic upgrade head
python scripts/seed.py

# 5. გაშვება
uvicorn app.main:app --reload
```

- API: http://localhost:8000/api/v1
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## Quality gates

```bash
ruff check . && ruff format --check .
mypy app
pytest -q
```

პროდაქშენის იმიჯი ცალკე უნდა შემოწმდეს — ის მხოლოდ `[project.dependencies]`-ს
იღებს, `.venv` კი `.[dev]`-საც. სხვაობა რეალურ ბაგს მალავდა (იხ. ASSUMPTIONS §8.11):

```bash
docker build -t voltbox-api:check .
docker run --rm -e DATABASE_URL=postgresql://u:p@h:5432/d   -e JWT_SECRET=0123456789012345678901234567890123456789   voltbox-api:check python -c "import app.main as m; print(len(m.app.openapi()['paths']), 'paths')"
```

## დამოკიდებულებების lock

`pyproject.toml`-ში range-ებია (`>=`). რეალურად ეყენებულ ვერსიებს lock-ები
წყვეტენ — ყველა ვერსია ფიქსირებულია, ყველა ფაილი sha256-ით მოწმდება:

| ფაილი | შონაარსი | ვინ იყენებს |
|---|---|---|
| `requirements.txt` | `[project.dependencies]` | Dockerfile → production-ის venv |
| `requirements-dev.txt` | იგივე + `dev` extra + editable build-ის hatchling | CI |
| `requirements-build.txt` | hatchling-ი და მის დამოკიდებულებები | Dockerfile → ცალკე build venv, image-ში არ ხვდება |

`requirements-dev.txt` `requirements.txt`-ის constraint-ით generate-დება: ყველა
საერთო პაკეტი იმავე ვერსიაზეა, ასე რომ CI ზუსტად prod-ის ვერსიებს ტესტავს.

Install-ი ყველგან `--require-hashes --only-binary=:all:`-ია. hash-ი wheel-ზე რომ
არ ემთხვეოდეს, `--only-binary`-ის გარეშე pip-ი refuse-ის ნაცვლად sdist-ზე
გადავიდოდა, და sdist-ის build backend-ი ვერსიისა და hash-ის გარეშე ჩამოიწერდა.
შედეგი: ახალ დამოკიდებულება, რომელსაც Linux/Python 3.14-ისთვის wheel-ი არ აქვს,
build-ს ხმამაღლა ჩერს — ეს განზრახაა.

### ⚠️ მხოლოდ Linux container-ში, Python 3.14-ზე — არასდროს laptop-ზე

pip-compile environment marker-ებს **იმ მანქანაზე** ამოწმებს, სადაც ეშვება, და
false-ად ამოწმებულ requirement-ს lock-იდან ჩუმად ამოაგდებს. `pyproject.toml`-ში
`gunicorn>=23.0; sys_platform != 'win32'` წერია, ასე რომ Windows-ზე generate-ებულ
lock-ში **gunicorn-ი არ იქნება**. იმიჯი აეწყობა, CI-ის `image` job-ი მწვანე იქნება —
`import app.main` gunicorn-ს არ იმპორტებს, ის მხოლოდ `CMD`-შია — container-ი კი
არ აიწევს. გაზომილი: Windows-ზე generate-ებულ lock-ში gunicorn-ი და uvloop-ი არ არის.

ეს ASSUMPTIONS §8.11-ის (`email-validator`) კლასია, ოღონდ უფრო ცუდი: import-ის
შემოწმება gunicorn-ს საერთოდ ვერ ხედავს. container-ი Dockerfile-ის base image-ია,
იმავე digest-ით — Dockerfile-ში მისი განახლებისას აქაც:

```bash
cd backend
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W 2>/dev/null || pwd)":/src -w /src python:3.14.7-slim-trixie@sha256:ef30e8ee3a7f227b0b5b39669b2e656f35b56b918c6631820357c2a55ff5a428 sh -c '
  pip install --quiet --root-user-action=ignore pip-tools==7.6.1 &&
  pip-compile --generate-hashes --allow-unsafe --strip-extras \
    --output-file requirements.txt pyproject.toml &&
  pip-compile --generate-hashes --allow-unsafe --strip-extras \
    --extra dev --build-deps-for editable --constraint requirements.txt \
    --output-file requirements-dev.txt pyproject.toml &&
  pip-compile --generate-hashes --allow-unsafe --strip-extras \
    --only-build-deps --build-deps-for wheel \
    --output-file requirements-build.txt pyproject.toml'
```

`MSYS_NO_PATHCONV` და `pwd -W` Git Bash-ისთვისაა; Linux/macOS-ზე ბრძანება ისეთი
ეშვება. რიგი მნიშვნელოვანია: `requirements-dev.txt` `requirements.txt`-ზე
დამოკიდებულია.

### დამოკიდებულების დამატება ან განახლება

1. `pyproject.toml`-ში შეცვალე.
2. ზემოთ მოცემული ბრძანება. pip-compile არსებულ pin-ებს ინახავს და მხოლოდ ახალს
   ამატებს; ერთ პაკეტის განახლებისთვის `--upgrade-package <name>` დაამატე
   შესაბამის `pip-compile`-ს.
3. **pyproject-ი და სამივე lock-ი — ერთ commit-ში.**

თუ 2-ი დამავიწყდება, `pip check`-ი image-ის build-ს და CI-ს აჩერებს
(`voltbox-backend … requires X, which is not installed`): `--no-deps` install-ი
lock-ის მიღმა არაფერს ჩამოწერს.

### ლოკალური venv

Quick start-ის `pip install -e ".[dev]"` lock-ის გარეშე რჩება: lock-ი Linux-ისთვის
resolve-ებულია, uvloop-ი კი Windows-ზე არ install-დება. lock-ი CI-ისა და
production-ის კონტრაქტია — ორივე Linux-ია.

## ადმინისტრატორები

ადმინი **მხოლოდ** ბრძანების ხაზიდან იქმნება. საჯარო რეგისტრაცია `role`-ს არ
იღებს (`RegisterRequest`-ს ასეთი ველი არ აქვს და `ApiRequest` უცნობ ველებს
კრძალავს), ასე რომ თავის თავს ვერავინ დააწინაურებს.

```bash
python scripts/manage_admin.py create-admin --email you@voltbox.ge --first-name გიორგი
python scripts/manage_admin.py promote-user --email someone@voltbox.ge
python scripts/manage_admin.py demote-user  --email someone@voltbox.ge
```

პაროლი **არასოდეს არის არგუმენტი** — ის shell-ის ისტორიაში, `ps`-ის გამონატანსა
და CI-ის ლოგებში დარჩებოდა. სკრიპტი მას ინტერაქტიულად კითხულობს, ან
`VOLTBOX_ADMIN_PASSWORD`-იდან (მაგ. CI-სთვის).

`demote-user` როლთან ერთად **ყველა refresh-ტოკენს აუქმებს**. ამის გარეშე
დაქვეითებული ადმინი 30 დღემდე შეძლებდა ახალი access-ტოკენების აღებას.
წვდომა მაშინვე ითიშება — `require_admin` როლს ყოველ მოთხოვნაზე ბაზიდან
კითხულობს და არა JWT-ის შიგთავსიდან.

---

## პროდუქტების დამატება

ბაზა ორ ნაწილად იყოფა:

| | რა არის | ცოცხალ ბაზაზე |
|---|---|---|
| **სტრუქტურა** — `categories`, `brands` | კონფიგია: `categories.filters` მთელ FilterSidebar-ს კვებავს | ✅ სჭირდება |
| **პროდუქტები** | `../frontend/src/data/products.js`-ის 61 ჩანაწერი სატესტოა | ❌ არ სჭირდება |

```bash
python scripts/seed.py --structure-only   # მხოლოდ კატეგორიები და ბრენდები
python scripts/seed.py                    # + 61 სატესტო პროდუქტი (ლოკალურისთვის)
```

### რეალური პროდუქტების იმპორტი

```bash
cp scripts/products.example.json products.json     # შეავსე
python scripts/import_products.py products.json --dry-run   # ჯერ შემოწმება
python scripts/import_products.py products.json             # მერე ჩაწერა
```

`slug` უნიკალური გასაღებია — ხელახლა გაშვება ჩანაწერს **ანახლებს** და არ ადუბლირებს.

სავალდებულო ველები: `slug`, `name`, `category` (slug-ით), `brand` (სახელით),
`price`. დანარჩენი არასავალდებულოა — სრული ნუსხა `scripts/products.example.json`-შია.

სკრიპტი ავტომატურად აგვარებს იმას, რაც ხელით შევსებისას ყველაზე ხშირად ტყდება:
- `category_id` / `brand_id` UUID-ების ამოხსნას სახელით
- **`search_text`-ის გამოთვლას** — მის გარეშე პროდუქტი კატალოგში ჩანს, ძებნა კი
  ვერ პოულობს
- სურათებს `position`-ითა და `is_primary`-ით

ვალიდაცია ჯერ ყველა ჩანაწერს ამოწმებს და მხოლოდ მერე წერს — ნახევრად შესრულებული
იმპორტი გამორიცხულია.

### თუ Supabase-ის Table Editor-ით დაამატე

ხელით ჩაწერილ პროდუქტს `search_text` ცარიელი დარჩება. გაასწორე:

```bash
python scripts/reindex_search.py
```

---

## ადმინ პანელი

### გარემოს ცვლადები

```dotenv
STORE_TIMEZONE=Asia/Tbilisi          # ნაგულისხმევი; "დღეს" ამ სარტყელში ითვლება
SUPABASE_PROJECT_REF=                # სურათებისთვის; ცარიელი = ლოკალური fake
SUPABASE_SERVICE_ROLE_KEY=           # მხოლოდ backend-ზე, არასოდეს ბრაუზერში
SUPABASE_STORAGE_BUCKET=product-images
MAX_IMAGE_BYTES=5242880              # 5 MB
MAX_IMAGE_DECODE_BYTES=104857600     # 100 MiB — ერთ ატვირთვის გაშლის ჭერი
```

### რა ზომის სურათი ავტვირთოთ

**ტელეფონის ჩვეულებრივი ფოტო (12 MP) — ზუსტად ის, რაც საჭიროა.** ზღვრები: 5 MB,
და JPEG-ზე 13.3 MP, PNG-ზე 8.3 MP, WebP-ზე 1.9 MP (WebP-ის გაშლა რამდენჯერმე
მეტ მეხსიერებას ჭამს, ამიტომ მისი ზღვარი უფრო დაბალია). პიქსელების ზღვარი
მხოლოდ 1600px-ს გადაცილებულ სურათს ეხება — რაც ამ ზომაშია, ისედაც უცვლელად
ინახება და არ იშლება.

**ეს ხარისხს არ ეხება.** ატვირთული სურათი ყოველთვის 1600px-მდე მცირდება
(`MAX_STORED_EDGE`), ასე რომ 24 MP-ის და 12 MP-ის ფოტო **ერთი და იმავე** შენახულ
სურათს იძლევა — უფრო დიდი ფაილი მხოლოდ მეხსიერებას ხარჯავს, რომელიც მაშინვე
გადაიყრება. თუ ტელეფონი 24 MP-ზე ან 48 MP-ზეა გადაყვანილი, კამერის პარამეტრებში
ჩვეულებრივ რეჟიმს დაუბრუნდით.

თუ ატვირთვა უარყოფილია, პანელი წერს, რა ზომამდე შევამციროთ.

### Storage-ის bucket

Supabase → Storage → New bucket, სახელი `product-images`, **Public** მონიშნული.

საჯარო განზრახაა: ხელმოწერილი URL-ები იწურება, შეკვეთის პოზიციები კი სურათის
მისამართს snapshot-ად ინახავენ — ორწლიანი შეკვეთის გატეხილი ბმული აღდგენას აღარ
ექვემდებარება. ჩაწერა მხოლოდ backend-ს შეუძლია service-role გასაღებით; ბრაუზერს
ის არასოდეს ხედავს.

გასაღებების გარეშეც მუშაობს — `get_storage()` მეხსიერების fake-ზე გადადის და
პანელი ლოკალურად ისე ეშვება, თითქოს bucket არსებობს.

### პირველი ადმინი

```bash
python scripts/manage_admin.py create-admin --email you@voltbox.ge --first-name გიორგი
```

მერე frontend-ში `/admin/login`.

### ლოკალურად გაშვება

```bash
# 1. backend
uvicorn app.main:app --reload

# 2. frontend — .env-ში VITE_API_MODE=http და VITE_API_BASE_URL=/api/v1
cd ../frontend && npm run dev
```

`/api/v1` შედარებითი გზაა და Vite-ის proxy-ზე გადის — ასე ადმინი ngrok-ითაც
მუშაობს და CORS საერთოდ არ ერევა.

---

## სიხშირის შეზღუდვა და proxy

ორი პარამეტრი, ორივე ჩუმად ტყდება — საიტი მუშაობს, ლიმიტი კი აღარ მოქმედებს.

```dotenv
REDIS_URL=redis://localhost:56379/0   # ცარიელი = მთვლელები ერთ პროცესში
FORWARDED_ALLOW_IPS=10.1.0.2          # ვის დაუჯეროს კლიენტის IP-ის შესახებ
```

**`REDIS_URL`** — მთვლელები ნაგულისხმევად პროცესის მეხსიერებაშია. Dockerfile ორ
worker-ს უშვებს, ანუ „5 შესვლა წუთში" რეალურად ათი ხდება, და მეექვსე მცდელობა
გადის თუ არა, დამოკიდებულია იმაზე, რომელ worker-ს მოხვდა.

Redis-ის გათიშვა საიტს არ აჩერებს: limiter იმავე ლიმიტებით პროცესის მეხსიერებას
უბრუნდება და პერიოდულად ცდილობს დაბრუნებას. ეს არც fail-open-ია (ბრუტფორსის
ზღვარი სწორედ მაშინ მოიხსნებოდა, როცა რაღაც უკვე გატეხილია) და არც
fail-closed (Redis-ის გათიშვა შესვლას აკრძალავდა) — დეგრადირებული რეჟიმია,
per-worker და არა საერთო, და ლოგში ჩანს.

**`FORWARDED_ALLOW_IPS`** — gunicorn ნაგულისხმევად მხოლოდ `127.0.0.1`-ს ენდობა.
თუ წინ reverse proxy დგას საკუთარი მისამართით, `X-Forwarded-For` უგულებელყოფილი
იქნება და **მთელი საიტი ერთ ლიმიტს გაიყოფს**. production/staging-ში მისი
არარსებობა გაშვებას აჩერებს; `*` აკრძალულია, რადგან მაშინ ნებისმიერს შეუძლია
header-ით თავისი IP აირჩიოს.

ლიმიტის გასაღები `request.client.host`-ია — header-ს ხელით არსად ვპარსავთ.

## Supabase

`DATABASE_URL` უნდა იყოს **Session pooler**-ის URI (არა Direct, არა Transaction).
სქემის (`postgresql://` → `postgresql+asyncpg://`) და `?sslmode=`-ის მოგვარებას
`app/core/config.py` თავად ახდენს — dashboard-იდან დაკოპირებული სტრიქონი უცვლელად ჩასვი.

## Layout

| გზა | პასუხისმგებლობა |
|---|---|
| `app/core/` | კონფიგი, უსაფრთხოება, შეცდომები, ლოგები, პაგინაცია |
| `app/db/` | ძრავი, სესია, SQLAlchemy მოდელები |
| `app/schemas/` | Pydantic request/response მოდელები (camelCase alias) |
| `app/api/v1/routes/` | თხელი router-ები — ვალიდაცია და სერვისის გამოძახება |
| `app/services/` | ბიზნეს-ლოგიკა: ფული, მარაგი, უფლებები |
| `alembic/` | მიგრაციები |
| `scripts/seed.py` | სტრუქტურა (+ სურვილისამებრ 61 mock პროდუქტი) |
| `scripts/import_products.py` | რეალური პროდუქტების იმპორტი JSON-იდან |
| `scripts/export_mock_data.mjs` | კითხულობს `../frontend/src/data/*.js`-ს seed-ისთვის |
| `tests/` | ტესტები (pytest + ცოცხალი Postgres) |
