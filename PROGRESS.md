# Progress

## Current Stage
Stage 1 — Audit fixes (closed by the owner 2026-10-10; T0–T14 done)

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

- [x] **T14 · should-fix · `scripts/verify_restore.py` reads `backend/.env` at import.**
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

Deploy plan (owner runs; nothing here was run against live — no alembic, no SQL, no push, no Render call).
Prepared 2026-10-10 for Stage 1 (code at `7a867fb`).

**1. Migrations on the live Supabase database**
- Stage 1 added exactly one migration: `0015` (RLS on `public.carts` and `public.alembic_version`).
  Live already shows RLS on 15/15 tables (advisor, owner), so on live it changes nothing but the
  recorded head. The backend works the same without it; run it so live and `alembic upgrade head`
  agree and a rebuilt database matches.
- The live head is **not known to me** (reading it was denied by the permission classifier;
  PROJECT.md Open Questions still asks it). Find it first in the SQL Editor:
  `select version_num from public.alembic_version;`
  Then run, in order, only the blocks **above** that value. Each block's last `UPDATE` checks the old
  value, so a block run on the wrong head updates 0 rows — look for `UPDATE 1`.
- The SQL below is `alembic upgrade A:B --sql` output per step (generated offline, 0010–0015), with every
  name hand-qualified with `public.` (Supabase has its own `auth.refresh_tokens`; the generated text is
  unqualified). Statement counts, to check a paste: 0010 = 3, 0011 = 2, 0012 = 4, 0013 = 2, 0014 = 5,
  0015 = 3, each between BEGIN and COMMIT.

```sql
-- 0009 -> 0010   (changes data: an order whose payment_method is not cash/card_on_delivery becomes 'cash')
BEGIN;
UPDATE public.orders SET payment_method = 'cash' WHERE payment_method NOT IN ('cash','card_on_delivery');
ALTER TABLE public.orders ADD CONSTRAINT ck_orders_payment_method_allowed CHECK (payment_method IN ('cash','card_on_delivery'));
UPDATE public.alembic_version SET version_num='0010' WHERE version_num = '0009';
COMMIT;

-- 0010 -> 0011
BEGIN;
CREATE INDEX ix_refresh_tokens_expires_at ON public.refresh_tokens (expires_at);
UPDATE public.alembic_version SET version_num='0011' WHERE version_num = '0010';
COMMIT;

-- 0011 -> 0012
BEGIN;
CREATE TABLE public.password_reset_tokens (
    user_id UUID NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_password_reset_tokens PRIMARY KEY (user_id),
    CONSTRAINT fk_password_reset_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT uq_password_reset_tokens_token_hash UNIQUE (token_hash)
);
ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_reset_tokens FORCE ROW LEVEL SECURITY;
UPDATE public.alembic_version SET version_num='0012' WHERE version_num = '0011';
COMMIT;

-- 0012 -> 0013
BEGIN;
ALTER TABLE public.orders ADD COLUMN lookup_token_hash VARCHAR(64);
UPDATE public.alembic_version SET version_num='0013' WHERE version_num = '0012';
COMMIT;

-- 0013 -> 0014
BEGIN;
ALTER TABLE public.categories ADD COLUMN name_en VARCHAR(150) DEFAULT '' NOT NULL;
ALTER TABLE public.brands ADD COLUMN name_en VARCHAR(150) DEFAULT '' NOT NULL;
ALTER TABLE public.products ADD COLUMN name_en VARCHAR(300) DEFAULT '' NOT NULL;
ALTER TABLE public.products ADD COLUMN description_en TEXT DEFAULT '' NOT NULL;
UPDATE public.alembic_version SET version_num='0014' WHERE version_num = '0013';
COMMIT;

-- 0014 -> 0015   (the only one Stage 1 added; RLS is already on live, so no visible change)
BEGIN;
ALTER TABLE public.carts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
UPDATE public.alembic_version SET version_num='0015' WHERE version_num = '0014';
COMMIT;
```
- Check after: `select version_num from public.alembic_version;` → `0015`; and
  `select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' and not c.relrowsecurity;` → no rows.
- 0010–0014 predate Stage 1. If live is already at 0014 (as PROJECT.md guesses), only the last block is left.

**2. Order**
1. Migrations (additive or no-ops for running code: new columns have defaults, RLS with no policy does not
   affect the backend role) — before any code that reads `lookup_token_hash`, `name_en` or `password_reset_tokens`.
2. Backend (`voltbox-api`).
3. Frontend (`voltbox-storefront`).
Why backend first: the new storefront sends `currentPassword` and caps lines at 10 units; the old API would
reject the unknown `currentPassword` field (email change fails), while the new API with the old storefront
refuses only an email change without a password and a cart line over 10. Either order has a window of a few
minutes; backend-first keeps browsing and checkout working in it.
Caveat: `render.yaml` has no `autoDeploy` key, so one push to `main` starts both services (each has its own
`buildFilter`) and the static site usually finishes first. For a strict order, turn auto-deploy off for the
storefront in the Render dashboard and trigger it after the API is healthy. I did not check that dashboard
setting. Nothing is pushed from here.

**3. Environment variables on Render**
- None new, none changed. `MAX_REQUEST_BODY_BYTES` (default 256 KB) is optional; `ORDER_RATE_LIMIT`
  (`5/minute;30/day`) is a constant in `core/rate_limit.py`, not an env variable. `VOLTBOX_NO_DOTENV` is for
  tests and probes only — do not set it on Render.
- Still true: `CORS_ORIGINS` must hold the exact storefront origin, because the storefront now sends
  credentials (T3); `FORWARDED_ALLOW_IPS` is still "Unverified" in the Backlog.

**4. D2 — remove `public` from Supabase's Data API (Dashboard → Settings → Data API → Exposed schemas)**
- Needed before public launch, not for this deploy. The backend does not use the Data API (no `rest/v1`,
  anon key or Supabase JS client in the repo — checked in the repo only, not in Render's env); Storage goes
  through the service-role key, a different API. RLS is already on every table, so today's exposure is
  "no policy, no rows".
- When: after migrations, backend and frontend are deployed and the checklist below passes. Then it is a
  separate, easily reverted step, and a failure after it is not confused with a failure of the deploy.
  Repeat checklist items 3, 6 and 7 after it.

**5. After the deploy (by hand)**
1. `GET <api>/api/v1/health/live` and `/health` → 200.
2. Sign in on the storefront; the login response sets a refresh cookie (DevTools → Application → Cookies).
   On onrender.com the session still ends after 30 minutes (Accepted Risk) — expected.
3. Guest order with one product × 10 → created; × 11 → refused; a 21st different product in the cart →
   the "at most 20 different products" message. The new order shows a started status timeline in the admin (T10).
4. Signed-in checkout, repeated with the same Idempotency-Key (double click / retry) → no error page.
5. Profile: change email without the current password → refused; with it → works.
6. Admin: upload a photo over 5 MB → "photo is over 5 MB" (T13); a normal photo → saved.
7. Admin: rename a brand → its products are found by the new name in search (T9).
8. Rate limit: the 6th order within a minute from one IP → 429 (use a test product and delete the test
   orders by hand in the admin afterwards).
9. Supabase Dashboard → Advisors: no new "RLS disabled" warning.

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
- Done: T13 (oversized photo says IMAGE_TOO_LARGE), T14 (verify_restore never reads `.env`; `--against` required, localhost only — owner approved).
- Verification: ruff, format, mypy, pytest 1009 — green, run by orchestrator. Frontend untouched since T12 (vitest 566, builds green).
- Known issues / blockers: executor ran the OLD verify_restore.py from backend/ to prove the new tests fail, so `backend/.env` was loaded into that one test process (nothing printed or sent; one failed localhost:55433 connect). Owner told.
- Next: Stage 1 has no open critical/should-fix; stage is Done pending owner.
