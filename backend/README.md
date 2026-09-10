# VoltBox Backend

FastAPI + PostgreSQL REST API for the VoltBox store. Replaces the frontend's mock
data layer without any component changes — only `VITE_API_MODE=http`.

> monorepo-ს ნაწილი. ზოგადი მიმოხილვა — [`../README.md`](../README.md),
> კლიენტის მხარე — [`../frontend/README.md`](../frontend/README.md).
> ყველა ქვემოთ მოცემული ბრძანება `backend/`-იდან სრულდება.

## Quick start

```bash
# 1. ბაზა (ლოკალური დეველოპმენტისთვის)
docker compose up -d db

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
| `tests/` | 110 ტესტი (pytest + ცოცხალი Postgres) |
