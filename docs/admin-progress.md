# Admin panel — run state

Source of truth for this run: `docs/admin-brief.md`.
Branch: `feature/admin-panel` (from `main` @ fc2b933).

---

## ⚠️ CRITICAL — database safety for this repo

`backend/.env` has `DATABASE_URL` pointing at **Supabase (remote, live)**.
Running `alembic upgrade head` or `pytest` with that env would touch the live
database. The brief forbids it ("never touch a remote or production database").

**Therefore, in this run, every migration and test command must set the URL
explicitly to the local Docker Postgres:**

```bash
# migrations (disposable DB, safe to drop)
DATABASE_URL=postgresql://voltbox:voltbox@localhost:55432/voltbox_mig alembic upgrade head

# tests (conftest reads TEST_DATABASE_URL and overrides DATABASE_URL itself)
TEST_DATABASE_URL=postgresql://voltbox:voltbox@localhost:55432/voltbox_test pytest -q
```

Local Postgres: container `voltbox-pg`, port **55432** (`backend/docker-compose.yml`).
Never run a bare `alembic` command in `backend/` while `.env` points at Supabase.

---

## Current phase

**Phase 0 — Discovery** (in progress)

---

## Done

- [x] Setup 1 — brief saved to `docs/admin-brief.md` (34.7 KB)
- [x] Setup 2 — working tree checked: clean at `fc2b933`, nothing of the user's at risk
- [x] Setup 3 — branch `feature/admin-panel` created from `main`
- [x] Setup 4 — this file created

---

## Discovery

_(Phase 0 findings go here)_

---

## Decisions to review

1. **Migrations run against a separate local DB, not `voltbox_test`.**
   Chosen: `voltbox_mig` on the local Docker Postgres for `upgrade`/`downgrade`
   checks, so migration experiments never race the test database.
   Why: `backend/.env` points at Supabase; a bare `alembic` command would hit
   production. Alternative considered: temporarily editing `.env` — rejected,
   too easy to forget to revert.

---

## Open items

_(bugs found outside scope, deferred work)_

---

## Last check results

_(actual summary lines from ruff / mypy / pytest / eslint / vitest / builds)_
