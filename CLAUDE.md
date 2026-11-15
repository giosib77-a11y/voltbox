# Project: VoltBox

`PROJECT.md` — მოთხოვნები და გადაწყვეტილებები (ადრინდელი — `ASSUMPTIONS.md`).
`PROGRESS.md` — მიმდინარე სტატუსი.

## Stack
- backend: Python 3.14, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL 17 (Supabase prod)
- frontend: React 18, Vite 8, Tailwind 3, React Router 7, i18next, vitest
- hosting: Render Blueprints (`backend/render.yaml`, `frontend/render.yaml`); CI: GitHub Actions

## უსაფრთხოება — ყოველთვის
- **ყოველ commit-მდე `git branch --show-current`. commit მხოლოდ `agent-system`-ზე ან `/auto`-ს და `/fix`-ის ბრენჩებზე (`team/...`, `fix/...`); `main`-ზე — არასდროს. სხვა შემთხვევაში გაჩერდი და მკითხე.**
- `git push`, `main`-ში merge — მხოლოდ მფლობელის თანხმობით.
- deploy არასდროს (Render-ზე არც trigger, არც env ცვლილება).
- `backend/.env` არ წაიკითხო და არ შეცვალო. ის ჩვეულებრივ **ლაივ Supabase-ზე** მიუთითებს.
  **ტესტებმაც, probe-ებმაც და ერთჯერადმა სკრიპტებმაც (მათ შორის scratchpad-ში, subagent-ის
  გაშვებულებმაც) `backend/.env` არასდროს უნდა წაიკითხონ.** `Settings` `.env`-ს cwd-იდან
  კითხულობს, ამიტომ `backend/`-იდან გაშვებული ნებისმიერი Python პროცესი მას ჩატვირთავდა
  (სხვა პროექტზე ასე გაჟონა key-ები). subagent-ის prompt-ში ეს წესი ცალკე ჩაწერე.
  დაცვა: `VOLTBOX_NO_DOTENV=1` (T0, PROGRESS.md) — `pytest` ამას თვითონ აყენებს, probe-ს ხელით
  უნდა მიეცეს; სანამ T0 არ დასრულებულა, probe გაუშვი `backend/`-ის გარეთ cwd-იდან.
- ლაივ ბაზაზე არასდროს: `alembic upgrade/downgrade/stamp`, `scripts/seed.py`,
  `scripts/import_products.py`, `scripts/delete_test_product.py`, `scripts/manage_admin.py`.
  migration ლაივზე მიდის მხოლოდ `alembic upgrade <from>:<to> --sql`-ით, ყველა სახელი
  `public.`-ით (Supabase-ს აქვს `auth.refresh_tokens`), და მფლობელი ჩასვამს SQL Editor-ში.
- ნებისმიერი `alembic`, `uvicorn` ან სკრიპტი ლოკალურად — მხოლოდ აშკარა ლოკალური
  `DATABASE_URL`-ით და ცარიელი `SUPABASE_PROJECT_REF`/`SUPABASE_SERVICE_ROLE_KEY`/
  `TELEGRAM_BOT_TOKEN`/`RESEND_API_KEY`/`REDIS_URL`-ით (env ცვლადი `.env`-ს ჯაბნის).
- ტესტები მხოლოდ ლოკალურად. `tests/conftest.py` `DATABASE_URL`-ს `TEST_DATABASE_URL`-ზე
  (ნაგულისხმევად `localhost:55432/voltbox_test`) აყენებს და გარე credentials-ს ცლის.
- **ტესტებისთვის საკუთარი pytest plugin-ები აკრძალულია** — არც `-p`-ით ჩატვირთვა, არც
  `PYTEST_PLUGINS`/`PYTEST_ADDOPTS`, არც დამატებითი/scratchpad conftest, არც სხვა გზა, რომელიც
  `app`-ს `tests/conftest.py`-მდე დააიმპორტებს ან conftest-ს გვერდს აუვლის (A-061: ასეთმა plugin-მა
  `backend/.env`-ის ლაივ URL დააქეშა და fixture-მა ლაივ Supabase-ზე `alembic downgrade base` გაუშვა).
  „ტესტი ძველ კოდზე ვარდება"-ს შემოწმება — მხოლოდ `git stash`-ით (იმპლემენტაციის ფაილები, ტესტი რჩება)
  ან ცალკე `git worktree`-ით, ჩვეულებრივი `pytest`-ით `backend/`-იდან (subagent-ს, რომელსაც git-ის
  ჩაწერა hook-ით აქვს დაბლოკილი: ძველი ვერსია `git show HEAD:<file>`-ით, მერე ახალი აღადგინე). ძალაში რჩება conftest-ის
  დაცვაც: ბაზა ლოკალური host + `_test`-ით დამთავრებული სახელი, სხვა შემთხვევაში run კავშირამდე ჩერდება;
  `alembic/env.py` ონლაინ რეჟიმში არალოკალურ host-ს უარყოფს, თუ `VOLTBOX_ALLOW_REMOTE_MIGRATION=1`
  არ არის (ეს ცვლადი agent-ს არასდროს დააყენოს).
- ახალი ცხრილის migration-ი **RLS-ს რთავს** (`ALTER TABLE public.<t> ENABLE ROW LEVEL SECURITY`) —
  Supabase-ის საჯარო API-ით სხვაგვარად გაიხსნება.

## Commands
ყველა backend ბრძანება `backend/`-იდან (Windows: `.venv/Scripts/<tool>.exe`),
frontend — `frontend/`-იდან.

- dev (backend): `docker compose up -d --wait db redis` → `DATABASE_URL=postgresql://voltbox:voltbox@localhost:55432/voltbox uvicorn app.main:app --reload`
- dev (frontend): `npm run dev` (`frontend/.env`-ში `VITE_API_MODE=mock|http`)
- lint: `cd backend && .venv/Scripts/ruff.exe check . && .venv/Scripts/ruff.exe format --check .`
- lint: `cd frontend && npm run lint`
- typecheck: `cd backend && .venv/Scripts/mypy.exe app scripts tests` (CI-ის ნაკრები; README-ის `mypy app scripts` ნაკლებია)
- test: `cd frontend && npm test`
- pytest (Stop hook-ში გამორთულია; /auto საბოლოო gate-ში უშვებს): `cd backend && TEST_DATABASE_URL=postgresql://voltbox:voltbox@localhost:55432/voltbox_hook_test TEST_REDIS_URL=redis://127.0.0.1:56379/2 .venv/Scripts/pytest.exe -q` (Stop hook-ის ხაზი: საკუთარი ბაზა, აგენტის pytest-ს არ ეჯახება)
- test (agents): `cd backend && .venv/Scripts/pytest.exe -q` (აგენტები ამას უშვებენ, voltbox_test)
  backend-ის ტესტებს სჭირდება `docker compose up -d --wait db redis` და ერთხელ
  `docker compose exec db createdb -U voltbox voltbox_test`.
- build: frontend `VITE_API_MODE=http VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run build`
  და იგივე `VITE_API_MODE=mock`-ით (CI ორივეს აშენებს) · backend image `docker build -t voltbox-api:check .`
- migrations (მხოლოდ ლოკალური ბაზა): `DATABASE_URL=postgresql://voltbox:voltbox@localhost:55432/voltbox alembic upgrade head`,
  შემდეგ იმავე `DATABASE_URL`-ით `alembic check` (CI-ში ორივე ეშვება)

### Quality gates (CI-ის ზუსტი ნაკრები)
- backend: `ruff check . && ruff format --check . && mypy app scripts tests && pytest -q`
- frontend: `npm run lint && npm test && npm run build` (ორივე `VITE_API_MODE`)
- **frontend-ის ცვლილება backend-ის სრულ gate-საც უშვებს** — backend-ის ტესტები
  `frontend/src`-ის ფაილებს კითხულობს (`grep -rn frontend backend/tests`).
- Dockerfile-ის ან დამოკიდებულებების ცვლილება — image build-იც. lock-ები მხოლოდ
  Linux container-ში იწერება (backend/README.md, „დამოკიდებულებების lock").

## Conventions
- კოდი, comments, commit messages — ინგლისურად; კომუნიკაცია — ქართულად.
- Commit message: Conventional Commits, subject აღწერს ქცევას (`fix(auth): a refresh rotating ... cannot outlive revoke_all`).
- ფული — `Decimal`/`Numeric(12,2)`; ფასი და ჯამი მხოლოდ სერვერზე.
- შეკვეთის სტატუსი იცვლება მხოლოდ `app/services/order_status.py`-ით; მარაგი — მხოლოდ `app/services/inventory.py`-ით.
- ვალიდაციის შეცდომა 400-ია (არა 422), კოდით (`code=...`); ახალ კოდს ტექსტი სჭირდება `frontend/src/i18n/ka.json`-ში და `en.json`-ში.
- storefront-ის ახალი ტექსტი — გასაღები ორივე i18n ფაილში; კომპონენტში ქართული ტექსტი პირდაპირ არა.
- ტესტის საერთო კოდი — `tests/factories.py`.
- გადაწყვეტილების მიზეზი — კომენტარში ან `PROJECT.md`-ის Decision Log-ში; შეზღუდვის აღწერისას ისიც თქვი, რა რჩება ძალაში.
- Docker container-ში რეპო მთლიანად არ კოპირდება და არ mount-დება — მხოლოდ საჭირო ფაილები (`backend/requirements*.txt`, `backend/pyproject.toml`); `backend/.env` container-ში არასდროს.
