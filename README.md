# VoltBox

ელექტრონიკისა და აქსესუარების ონლაინ-მაღაზია. ინტერფეისის ენა — ქართული,
ვალუტა — ₾ (GEL).

Monorepo ორი თანაბარმნიშვნელოვანი ნაწილით:

| | ტექნოლოგია | დოკუმენტაცია |
|---|---|---|
| [`frontend/`](./frontend/) | React 18 · Vite 5 · Tailwind 3 · React Router 6 | [frontend/README.md](./frontend/README.md) |
| [`backend/`](./backend/) | Python 3.14 · FastAPI · SQLAlchemy 2 · PostgreSQL | [backend/README.md](./backend/README.md) |

---

## სტრუქტურა

```
voltbox/
├── frontend/          React SPA
│   ├── src/           components, pages, context, hooks, services, data, utils
│   ├── public/        favicon + 183 დაგენერირებული SVG
│   ├── scripts/       gen-images.mjs
│   ├── .env           ← VITE_API_MODE (mock | http)   [კომიტდება]
│   └── vite.config.js  package.json  tailwind.config.js  postcss.config.js
│
├── backend/           FastAPI REST API
│   ├── app/           core, db, schemas, api/v1/routes, services
│   ├── alembic/       მიგრაციები
│   ├── scripts/       seed.py, import_products.py, reindex_search.py, export_mock_data.mjs
│   ├── tests/         110 ტესტი
│   ├── .env           ← DATABASE_URL, JWT_SECRET       [კომიტდება არ უნდა]
│   └── pyproject.toml  alembic.ini  docker-compose.yml  Dockerfile
│
├── .github/workflows/ frontend.yml · backend.yml
├── README.md          ეს ფაილი
├── ASSUMPTIONS.md     მიღებული ტექნიკური გადაწყვეტილებები და მათი მიზეზები
└── ROADMAP.md         რაზეც ვისაუბრეთ და განზრახ გადავდეთ
```

### ორი `.env` — არ აგერიოს

| ფაილი | ვინ კითხულობს | Git-ში |
|---|---|---|
| `frontend/.env` | Vite (**ბილდის დროს**) | ✅ კომიტდება — საიდუმლო არაფერია |
| `backend/.env` | FastAPI (**გაშვების დროს**) | ❌ იგნორირებულია — შეიცავს ბაზის პაროლს და `JWT_SECRET`-ს |

`backend/.env.example` და `frontend/.env.example` ნიმუშებია.

---

## გაშვება

ორივე ბრძანება **თავის საქაღალდეში** სრულდება.

### Frontend

```bash
cd frontend
npm install
npm run dev            # → http://localhost:5173
```

ნაგულისხმევად `VITE_API_MODE=mock` — backend საერთოდ არ სჭირდება, მონაცემები
მეხსიერებიდან მოდის.

### Backend

```bash
cd backend
docker compose up -d db                    # ლოკალური Postgres
cp .env.example .env                       # DATABASE_URL, JWT_SECRET
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"    # Windows
alembic upgrade head
python scripts/seed.py                     # სტრუქტურა + 61 სატესტო პროდუქტი
uvicorn app.main:app --reload              # → http://localhost:8000/docs
```

ცოცხალ (Supabase) ბაზაზე კი — `--structure-only`, რომ სატესტო პროდუქტები
არ მოხვდეს:

```bash
python scripts/seed.py --structure-only
```

### ორივე ერთად

`frontend/.env`-ში:

```dotenv
VITE_API_MODE=http
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

გადამრთველი **ბილდის დროს** მუშაობს (`vite.config.js` → `resolve.alias`),
ამიტომ ცვლილების შემდეგ dev-სერვერი თავიდან უნდა გაეშვას.

---

## Quality gates

| | ბრძანება |
|---|---|
| frontend | `cd frontend && npm run build` |
| backend | `cd backend && ruff check . && ruff format --check . && mypy app && pytest -q` |
| backend-ის იმიჯი | `cd backend && docker build -t voltbox-api:check .` |

იგივეს ამოწმებს CI — [`.github/workflows/`](./.github/workflows/). frontend
ორივე რეჟიმში (`mock` და `http`) აშენდება, backend კი ცოცხალ Postgres-ზე გადის.

იმიჯი განზრახ ცალკე მოწმდება: ის მხოლოდ `[project.dependencies]`-ს იღებს,
`.venv` კი `.[dev]`-საც — ამ სხვაობაში ერთხელ უკვე დაიმალა ბაგი, რომელსაც
110 მწვანე ტესტი ვერ ხედავდა ([ASSUMPTIONS.md §8.11](./ASSUMPTIONS.md)).

---

## რა სად წყდება

| კითხვა | პასუხი |
|---|---|
| საიდან მოდის მონაცემები? | `frontend/src/services/api.js` — ერთადერთი კონტრაქტი UI-სთვის |
| როგორ ემატება ახალი კატეგორია? | `frontend/src/data/categories.js` + `categories.filters` → FilterSidebar თვითონ აეწყობა |
| როგორ ემატება რეალური პროდუქტი? | ადმინ პანელიდან (`/admin/products`), ან `cd backend && python scripts/import_products.py products.json` |
| რატომ ასეა და არა სხვანაირად? | [ASSUMPTIONS.md](./ASSUMPTIONS.md) |
| რა დარჩა გასაკეთებელი? | [ROADMAP.md](./ROADMAP.md) |
| როგორ მუშაობს ადმინ პანელი? | [docs/admin-brief.md](./docs/admin-brief.md) · [backend/README.md](./backend/README.md#ადმინ-პანელი) |
