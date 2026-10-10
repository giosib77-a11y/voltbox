# Progress

## Current Stage
Stage 1 — Audit fixes

Source: full audit 2026-10-10 (standard-reviewer, three slices: auth/authz/privacy;
money/stock/data/Supabase; frontend/config/CI/Docker). Every task below was
re-checked in the code before it was written here. Order = suggested order.

## Tasks

- [x] **T0 · config · Nothing but a deliberate opt-in may read `backend/.env`.**
  Owner's rule (2026-10-10): tests and probes never read `backend/.env`. `Settings`
  (`app/core/config.py:70`) reads `.env` from the cwd, so every `pytest` run and every
  probe started in `backend/` loads the live Supabase URL and keys into the process.
  Fix: `env_file=None` when `VOLTBOX_NO_DOTENV=1`; `tests/conftest.py` sets it before the
  first import; a test that fails if `Settings` would open a `.env` under pytest.
  CLAUDE.md already states the rule.

- [x] **T1 · critical · Refresh-token reuse detection is rolled back.**
  `routes/auth.py` `refresh` raises without committing; `get_db` rolls back, so
  `_handle_possible_reuse`'s family revoke (`services/auth.py:263`) never persists.
  A stolen refresh cookie used first keeps its family alive. Tests pass only because
  `conftest.py`'s `override_get_db` never rolls back.
  Fix: commit on `UnauthorizedError` from the reuse path, as `/login` does, without
  persisting the claim of a disabled account (`services/auth.py:364`); a test whose
  `get_db` override rolls back on exception, proving the family stays revoked.

- [x] **T2 · should-fix · No migration enables RLS on `carts` and `alembic_version`.**
  `0009_saved_cart.py` creates `carts` without RLS; `alembic_version` is created by
  Alembic itself. A database built with `alembic upgrade head` exposes both through
  Supabase's public Data API. Nothing tests for it.
  Fix: migration `0015` enabling RLS on both (`public.`-qualified); a test that no
  `public` table has `relrowsecurity = false`; same check in `scripts/verify_restore.py`.
  Live DB: the Supabase advisor already shows RLS on 15/15 tables (owner, 2026-10-10),
  so no live SQL is needed. The migration only makes a rebuilt database match. If it is
  ever applied to Supabase, the owner runs the generated `public.`-qualified SQL and
  sees it first — never `alembic upgrade` from here.

- [x] **T3 · should-fix · Login/register/logout requests omit `credentials: 'include'`.**
  `frontend/src/services/httpClient.js:172` uses fetch's default (`same-origin`).
  The storefront calls the API cross-origin (onrender today, `voltbox.ge` →
  `api.voltbox.ge` later), so the refresh cookie from login is never stored, every
  session ends at 30 minutes (admin form included), and logout cannot revoke anything.
  Fix: send credentials on API requests (at least the auth calls) + a test asserting it.

- [x] **T4 · should-fix · Checkout with an expired token silently becomes a guest order.**
  `core/deps.py:73` `get_optional_user` returns `None` for an invalid Bearer token;
  the client refreshes only on 401. The order is saved with `user_id = NULL`: missing
  from "my orders", no confirmation email.
  Fix: header absent → guest; header present but invalid → 401 `INVALID_TOKEN`
  (client refreshes and retries with the same Idempotency-Key). Tests for both.

- [x] **T5 · should-fix · Logged-in duplicate checkout returns 500.**
  `services/order.py:273` `db.rollback()` expires the session's `user`; `owns_order`
  then reads `user.id` (lazy load in async → `MissingGreenlet`). The order exists,
  the shopper sees an error. Concurrency tests only use `user=None`.
  Fix: capture `user.id` before the claim (or claim in a savepoint); concurrent
  duplicate test with a signed-in user.

- [x] **T6 · should-fix · Email change needs no password.**
  `PATCH /auth/me` (`services/auth.py:558`) changes the email with only an access
  token; existing reset links survive. Token (XSS / shared computer) → change email →
  forgot-password → account taken over, once email sending is on.
  Fix: require and verify `currentPassword` when the email actually changes; delete
  the account's `password_reset_tokens` row. Frontend `Profile.jsx` asks for it only then.

- [x] **T7 · should-fix · `POST /orders` has only the 60/min default limit.**
  One IP can place ~60 guest orders a minute (50 lines × 99 units), holding the whole
  catalogue out of stock and flooding the owner's Telegram; `INSUFFICIENT_STOCK`
  returns the exact `available`. Fix: dedicated `ORDER_RATE_LIMIT` (e.g.
  `5/minute;30/day`) on `create_order` + a route-level test.

- [x] **T12 · should-fix · Guest order size cap (decided, was D3).**
  Owner's rule (2026-10-10): at most 20 distinct products per order, at most 10 units of
  each. Today 50 lines × 99 units (`schemas/order.py:22,63`). Applies to every order,
  not only guests' (one schema). Fix: `max_length=20`, `qty le=10`; the frontend cart
  must stop offering more than 10 per line / 20 lines (check `QuantityStepper`, cart
  reducer) and say why; update `PROJECT.md` Business Rules; tests at 20/21 and 10/11.

- [x] **T8 · should-fix · No request body size limit.**
  Nothing caps the body before JSON parsing; a 24 MB unauthenticated body measured
  ~250 MB of worker memory locally (validation 400 comes after). Render free has
  512 MB for two workers. Fix: ASGI middleware → 413 above ~64 KB (counting chunked
  bodies too), with the image-upload route allowed `MAX_IMAGE_BYTES` + overhead; tests.

- [x] **T9 · should-fix · Renaming a brand or category leaves `search_text` stale.**
  `services/admin_catalog.py` `update_brand` / `update_category` change the row only;
  `search_text` embeds brand name, category name and slug. Exact search stops finding
  those products until someone runs `scripts/reindex_search.py`.
  Fix: recompute `search_text` for the affected products in the same transaction
  when `name`/`slug` changes; test.

- [x] **T10 · should-fix · Checkout writes no status-history start row.**
  Only `order_status.transition` writes `OrderStatusHistory`; migration 0004
  backfilled `pending → pending` so every order has a timeline start. New orders
  show an empty history in the admin until the first transition.
  Fix: write the same start row in `place_order`'s transaction; update
  `tests/test_inventory.py:162`.

- [x] **T11 · should-fix · Backend CI skips frontend files its tests read.**
  `.github/workflows/backend.yml` paths list only `httpClient.js`; tests also read
  `frontend/src/i18n/ka.json`, `frontend/src/constants/index.js`,
  `frontend/src/admin/statuses.jsx`. A frontend-only PR can turn main red.
  Fix: add the three paths (and the README gates line, see Backlog nit).

- [x] **T13 · should-fix · T8 turned an oversized photo's message into "request too large, shorten the text".**
  `core/body_limit.py` answers 413 `PAYLOAD_TOO_LARGE` for an image upload past
  `max_image_bytes + 64 KB` (declared length and chunked), so the route's `IMAGE_TOO_LARGE`
  with `maxBytes` (`services/storage.py:178`, `httpClient.js:92`) is reached only inside the
  64 KB window. The owner uploading a 6–8 MB phone photo sees the wrong text. Reviewer
  reproduced it; the code and `main.py:38` confirm it.
  Fix: on the upload route both refusal paths answer `IMAGE_TOO_LARGE` with
  `{"maxBytes": settings.max_image_bytes}` (`limit_for` returns code/details with the limit);
  a test in `test_body_limit.py` for the upload 413's `code` and `maxBytes`, declared and chunked.

- [ ] **T14 · should-fix · `scripts/verify_restore.py` reads `backend/.env` at import.**
  `verify_restore.py:38` calls `dotenv_values(.../.env)` to learn the live URL it must refuse.
  CLAUDE.md: no script may read `backend/.env`; `VOLTBOX_NO_DOTENV` is not honoured here
  (T0 covered only `Settings`). Pre-existing.
  Fix: honour `VOLTBOX_NO_DOTENV=1` (no read, `LIVE_URL = None`) and keep the live-URL refusal
  working another way (e.g. refuse any `--against` host that is not localhost); a test for both.

## Backlog (needs user decision)

- `restoreItem` (cart undo) fails silently if the cart filled up meanwhile (low).
- Backend tests for 51 lines / qty 100 could sit at 21 / 11 (low).

Decided by the owner (2026-10-10):
- **D1 · onrender.com sessions.** Buying `voltbox.ge` + `api.voltbox.ge`; until then
  30-minute sessions are accepted (`onrender.com` is on the Public Suffix List, so a
  `SameSite=strict` cookie cannot cross storefront → API). Recorded in PROJECT.md
  Accepted Risks and in the Before-live list below. The `config.py:121` comment still
  says "same-origin" — change it to "same-site" with T3.
- **D2 · Extensions.** Do not move them. Checked: nothing in the repo uses the Supabase
  Data API (no `rest/v1`, anon key or Supabase JS client; only Storage via the
  service-role key). So: Deploy plan step for the owner — Supabase Dashboard → Data API
  settings → remove `public` from the exposed schemas. `unaccent` is unused (droppable).
- **D3 · Order size.** Became T12.
- **D4 · Reset-address limit (3/h) can be used against someone else's address.**
  Stays here; no change planned.

Before going live on `voltbox.ge` (owner's list):
- Buy the domain; move `CORS_ORIGINS`, `SITE_URL`, `connect-src`, the sitemap rewrite
  back (`grep -rn TEMP-ONRENDER backend/render.yaml frontend/render.yaml`).
- Sessions stop being limited to 30 minutes only once storefront and API are same-site.
- Supabase Dashboard: remove `public` from the Data API exposed schemas (D2).
- Plan 0.5c-512mb and the refresh-token prune cron back (docs/deployment.md §2).

Deploy plan (owner runs; not done from here): see the list above plus, after each
fix that changes behaviour, a push to `main` triggers Render's autoDeploy of the
storefront — nothing is pushed without approval.

Nits:
- Profile.jsx:92 inline current-password error never shows in http mode (`details.code`, not `details.currentPassword`; same in ChangePassword.jsx:54); only the toast appears.
- Partial add to a full-ish cart (8 + 5) shows only the error toast although 2 were added.
- Over-20 carts are cut silently, and differently: frontend `sanitize` keeps the first 20, backend `merge_cart` the last 20.
- Refresh 429/5xx logs the user out (`session.js:186`); only 401 should.
- Access log hides query only under `/api/v1/auth`; admin search `?q=` writes customer
  email/phone to logs (`core/logging.py:39`).
- Register / profile email check-then-insert: concurrent duplicate → 500, not 409.
- `jwt.decode` without `require` option; `jwt_algorithm` free string (defense in depth).
- No cap on saved addresses per user.
- `delete_product` deletes Storage files before the commit (`admin_product.py:451`).
- PATCH with `null` on NOT NULL fields → 500; `{"slug": ""}` writes an empty slug.
- `import_products.py` update path re-activates archived products, orphans images,
  resets stock.
- RLS `FORCE` used in 0001/0012 but not 0003/0004 (align in T2's migration if cheap).
- `orders.user_id ON DELETE SET NULL` conflicts with the `owner_or_guest_contact` CHECK.
- Order number date uses UTC, not `Asia/Tbilisi` (00:00–04:00 orders get the previous day).
- `carts.updated_at` never changes after the first write.
- Downgrades 0013/0014 destroy data without a warning in the docstring.
- `seed.py` has no guard against a non-local `DATABASE_URL` (README teaches plain
  `python scripts/seed.py`, and `.env` points at live).
- Production build silently falls back to mock when `VITE_API_MODE` is unset.
- `scripts/e2e/up.sh` blanks only `SUPABASE_*`; Telegram/Resend/Redis creds from
  `.env` stay live during local e2e orders.
- README gates (`mypy app scripts`, frontend `npm run build` only) differ from CI.
- Auth 5/min decorators have no route-level test.
- `docker-compose.yml` publishes Postgres/Redis on all interfaces.

Unverified (check before acting):
- `FORWARDED_ALLOW_IPS` value on Render — if wrong, all clients share one bucket.
- Render health check vs the 60/min default limit (429 restart loop?).
- Redis client has no socket timeouts (a blackholed Redis could stall a worker).
- Supabase session-pooler size vs the 30-connection budget.
- Render edge body-size limit; multipart image body parsed before `require_admin`.
- Two concurrent first-image uploads → 500 + orphaned file.

## Run State
- Finish-check this stage: done
- Fix rounds this stage: 1/2
- Failed attempts: —

## Last Session
- Date: 2026-10-10
- Done: T12 (order and cart cap 20 lines / 10 units, shared `core/limits.py`, storefront clamps and explains).
- Verification: ruff, format, mypy, pytest 993, eslint, vitest 566, http and mock builds — green, run by orchestrator.
- Known issues / blockers: new tests not run against the old code; no browser check; Georgian wording unreviewed.
- Next: stage tasks done — finish-check not run.
