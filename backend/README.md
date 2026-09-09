# VoltBox Backend

FastAPI + PostgreSQL REST API for the VoltBox store. Replaces the frontend's mock
data layer without any component changes — only `VITE_API_MODE=http`.

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
| `scripts/seed.py` | 61 mock პროდუქტის ჩატვირთვა |
