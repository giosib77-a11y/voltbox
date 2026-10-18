# Progress

## Current Stage
Stage 2 — Order trash (admin)

Source: the owner's request (2026-10-18): delete an order in the admin into a trash (with a
confirmation dialog), restore it with one button, delete it for good by hand or automatically
after 30 days; admin only; deleting never changes stock. Rules: PROJECT.md → Business Rules →
"Order trash"; endpoints: PROJECT.md → API Contract; reasons: Decision Log 2026-10-18.
Planned 2026-10-18; nothing implemented yet. Order = suggested order: T18 first; then T19, T21
and T23 can run side by side (no shared files); T20 after T19; T22 last.

Rules for every task of this stage (CLAUDE.md, repeated because subagents run them):
- Never read or open `backend/.env`; tests and probes run with `VOLTBOX_NO_DOTENV=1`
  (`pytest` sets it itself). Every `alembic` / script run gets `VOLTBOX_NO_DOTENV=1` and an
  explicit local `DATABASE_URL` (`postgresql://voltbox:voltbox@localhost:55432/...`).
- Nothing runs against the live database. Migration 0016 reaches live only as reviewed SQL
  the owner pastes (T23).
- Backend gate: `ruff check . && ruff format --check . && mypy app scripts tests && pytest -q`.
  Frontend gate: `npm run lint && npm test && npm run build` with `VITE_API_MODE=http` and
  `VITE_API_MODE=mock`. A change to any file under `frontend/src` runs both gates.

## Tasks

- [x] **T18 · Migration 0016: `orders.deleted_at` + partial index**
  owner: backend-dev
  files: backend/alembic/versions/0016_orders_deleted_at.py (new), backend/app/db/models/orders.py, backend/tests/test_order_trash_schema.py (new)
  depends: —
  What: `orders.deleted_at TIMESTAMPTZ NULL` (no default) and
  `ix_orders_deleted_at (deleted_at) WHERE deleted_at IS NOT NULL`. The model declares both
  (`Index(..., postgresql_where=text("deleted_at IS NOT NULL"))`, with a comment like the one on
  `ix_orders_status`) so `alembic check` stays clean. No new table, so no RLS change. Downgrade
  drops the column and index; its docstring says what that does: every trashed order becomes a
  live order again (the trash state is lost), nothing else is touched.
  done when: `tests/test_order_trash_schema.py` passes: `deleted_at` is `timestamp with time zone`,
  nullable, no default; `ix_orders_deleted_at` exists and its predicate is
  `deleted_at IS NOT NULL`. `tests/test_schema.py` (RLS on every table) still green. Locally, with
  `VOLTBOX_NO_DOTENV=1` and `DATABASE_URL=postgresql://voltbox:voltbox@localhost:55432/voltbox`:
  `alembic upgrade head` then `alembic check` → no new operations. (pytest's conftest runs the
  migrations down and up, so the downgrade is exercised too.) Backend gate green.

- [x] **T19 · Trash and restore; status frozen in the trash; the trash list**
  owner: backend-dev
  files: backend/app/services/order_trash.py (new), backend/app/services/admin_orders.py, backend/app/services/order_status.py, backend/app/schemas/admin_orders.py, backend/app/api/v1/routes/admin/orders.py, frontend/src/i18n/ka.json, frontend/src/i18n/en.json, backend/tests/test_order_trash.py (new)
  depends: T18
  What:
  - `services/order_trash.py`: `TRASH_RETENTION = timedelta(days=30)` — the only place the 30
    days live; `trash(db, order_id)` and `restore(db, order_id)`, each returning the order and
    whether it changed. Both lock the row `FOR UPDATE` through the state machine's lock (make
    `order_status._lock_order` public as `lock_order` — one copy). Trash on a trashed order and
    restore on a live one change nothing (`deleted_at` keeps its first value).
  - Routes: `POST /admin/orders/{id}/trash`, `POST /admin/orders/{id}/restore` → 200
    `OrderDetailOut`; audit `order.trash` / `order.restore` (actor = admin,
    `changes: {status, deletedAt}`) **only when something changed**, same transaction; commit.
    `GET /admin/orders` gets `trash: bool = False`.
  - `order_status.transition`: after the lock, a trashed order → 409 `ORDER_IN_TRASH`, before
    the `INVALID_TRANSITION` check. `counts_by_status` counts live orders only.
  - `admin_orders`: `_conditions(..., trash)` adds `deleted_at IS NULL` (default) or
    `IS NOT NULL` (`trash=true`, ordered `deleted_at DESC, id`); `_summary` adds `deleted_at` and
    `purge_at` (`deleted_at + TRASH_RETENTION`, else None); `get_order` returns
    `allowed_transitions = []` for a trashed order and still returns it.
  - `schemas/admin_orders.py`: `OrderListItem` gains `deleted_at: datetime | None`,
    `purge_at: datetime | None` (so `OrderDetailOut` has them too).
  - `apiErrors.ORDER_IN_TRASH` in `ka.json` and `en.json` (e.g. "შეკვეთა სანაგვეშია — ჯერ
    აღადგინეთ." / "This order is in the trash — restore it first.").
  - Known, left as is: `services/order.py` `cancel` (no route calls it) would turn
    `ORDER_IN_TRASH` into `ORDER_NOT_CANCELLABLE`; that file is T21's.
  done when: `tests/test_order_trash.py` passes, covering: trash → 200, `deletedAt` set,
  `purgeAt` = `deletedAt` + 30 days, exactly one `order.trash` audit row with the admin as actor;
  trash again → same `deletedAt`, still one audit row; restore → same `status` as before, both
  fields null, one `order.restore` row; restore a live order → 200, no audit row; trash and
  restore of an unknown id → 404 `ORDER_NOT_FOUND`; `POST /status` (pending → cancelled) on a
  trashed order → 409 `ORDER_IN_TRASH`, and status, product stock, `inventory_movements` count
  and `order_status_history` count unchanged; trashing a pending order leaves product stock and
  `inventory_movements` unchanged; the detail of a trashed order → 200 with
  `allowedTransitions: []`; default list hides it (`total` counts live orders only);
  `trash=true` lists only trashed orders, newest deletion first, with `q` and `status` still
  applied; `counts_by_status` excludes it. `tests/test_admin_auth.py` covers the new routes
  (anonymous 401, customer 403) with no edit; `tests/test_error_messages.py` green. Backend gate
  green; frontend gate green (JSON changed: `i18n.test.js` key parity).

- [ ] **T20 · Permanent delete and the 30-day purge**
  owner: backend-dev
  files: backend/app/services/order_trash.py, backend/app/api/v1/routes/admin/orders.py, frontend/src/i18n/ka.json, frontend/src/i18n/en.json, backend/tests/test_order_purge.py (new)
  depends: T19
  What:
  - `delete_forever(db, order_id)`: lock the row; missing → 404 `ORDER_NOT_FOUND`; live → 409
    `ORDER_NOT_IN_TRASH`; else audit `order.purge` (`{orderNumber, status, total,
    automatic: false}`, actor = admin) and delete — items and history go by CASCADE,
    `inventory_movements.order_id` becomes NULL by its FK. Route `DELETE /admin/orders/{id}` → 204.
  - `purge_expired(db) -> int`: one `DELETE FROM orders WHERE deleted_at < now() - TRASH_RETENTION
    RETURNING id, order_number, status, total`, one `order.purge` audit row per order (actor
    NULL, `automatic: true`). `GET /admin/orders` (both modes) calls it and commits before the
    list query.
  - Stock: neither function calls `adjust_stock` or writes `inventory_movements`.
  - `apiErrors.ORDER_NOT_IN_TRASH` in `ka.json` and `en.json` (e.g. "სამუდამოდ იშლება მხოლოდ
    სანაგვეში მყოფი შეკვეთა." / "Only an order in the trash can be deleted for good.").
  done when: `tests/test_order_purge.py` passes, covering: `DELETE` on a live order → 409
  `ORDER_NOT_IN_TRASH`, order intact; on an unknown id → 404; on a trashed order → 204, the order,
  its `order_items` and `order_status_history` rows gone, its `inventory_movements` rows still
  there with `order_id IS NULL`, product stock unchanged, one `order.purge` row (actor = admin,
  `automatic` false); an order trashed 31 days ago (set `deleted_at` directly) is gone after
  `GET /admin/orders` and after `GET /admin/orders?trash=true`, with an `order.purge` row (actor
  NULL, `automatic` true) and stock unchanged; one trashed 29 days ago and live orders are
  untouched; concurrency (two sessions, as in `tests/test_orders_concurrency.py`): a restore
  holding the row lock while `purge_expired` runs → after the restore commits, the purge
  deletes 0 rows and the order is live; purge first → the restore answers 404. Backend gate
  green; frontend gate green (JSON changed).

- [ ] **T21 · Hide trashed orders from customers, guests, the dashboard and admin customers**
  owner: backend-dev
  files: backend/app/services/order.py, backend/app/services/dashboard.py, backend/app/services/admin_customers.py, backend/tests/test_order_trash_hidden.py (new)
  depends: T18
  What: `Order.deleted_at.is_(None)` in `order.list_for_user`, `get_by_number`,
  `get_guest_order` (the same `order_not_found()` 404); in the dashboard's sales today, orders
  today, sales total, top products and latest orders; in `admin_customers`'
  `_orders_count_subquery`, `_total_spent_subquery` and `get_customer`'s order list. The two
  idempotency lookups in `place_order` (`services/order.py:239`, `:281`) stay unfiltered on
  purpose — a comment says why (a replay must never place a second order). `counts_by_status`
  is T19's. Tests set `deleted_at` directly, so this task does not wait for T19;
  `tests/factories.py` is not changed.
  done when: `tests/test_order_trash_hidden.py` passes, covering: a trashed order is missing
  from `GET /orders`; `GET /orders/{number}` → 404 `ORDER_NOT_FOUND`; the guest
  `POST /orders/lookup` with the right token → 404 with a body identical to an unknown
  number's; dashboard `salesToday`, `ordersToday`, `salesTotal`, `topProducts`, `latestOrders`
  leave out a trashed delivered order and count it again once `deleted_at` is NULL; admin
  customers list (`ordersCount`, `totalSpent`) and detail (`orders`, `ordersCount`,
  `totalSpent`) leave it out; a replay of `POST /orders` with a trashed order's
  `Idempotency-Key` (guest and signed-in) → the same `orderNumber`, order count unchanged,
  stock decremented once, no new `inventory_movements` row. Backend gate green.

- [ ] **T22 · Admin trash UI (OrderDetail, OrderList)**
  owner: frontend-dev
  files: frontend/src/admin/adminApi.js, frontend/src/admin/pages/OrderList.jsx, frontend/src/admin/pages/OrderDetail.jsx, frontend/src/admin/pages/OrderList.test.jsx (new), frontend/src/admin/pages/OrderDetail.test.jsx (new)
  depends: T19, T20
  What (Georgian text in the components, as in the rest of `src/admin`; no i18n keys):
  - `adminApi.js`: `trashOrder(id)` (POST `/admin/orders/:id/trash`), `restoreOrder(id)` (POST
    `.../restore`), `deleteOrderForever(id)` (DELETE `/admin/orders/:id`); `listOrders` passes
    `trash`.
  - OrderDetail: "წაშლა" → `ConfirmDialog`; for pending/confirmed/processing the description
    says the units stay reserved and to cancel first if they should return → `trashOrder` →
    navigate to `/admin/orders` with a success toast (`useToast`). A trashed order (`deletedAt`
    set): a banner with the purge date (`purgeAt`), no status buttons, "აღდგენა" (one click, no
    dialog, the page shows the live order) and "სამუდამოდ წაშლა" (`ConfirmDialog` saying it
    cannot be undone → `deleteOrderForever` → `/admin/orders?trash=true`).
  - OrderList: a "სანაგვე" toggle bound to `?trash=true` (like the other filters, resets the
    page); in the trash: deletion date and days left (from `purgeAt`, never below 0), per-row
    "აღდგენა" and "სამუდამოდ წაშლა" (`ConfirmDialog`), the list reloads after each.
  - Errors: the message from the existing `apiErrors` lookup (`error.message`), shown in the page
    or the dialog; buttons usable again after a failure.
  done when: `OrderDetail.test.jsx` and `OrderList.test.jsx` (mocked `adminApi`, as
  `ProductList.test.jsx` does) pass, covering: the delete dialog shows the stock warning for
  `pending` and not for `delivered`; confirm calls `trashOrder` once and lands on the list; a
  trashed order shows the purge date, no status buttons, restore calls `restoreOrder` without a
  dialog; permanent delete needs the dialog and calls `deleteOrderForever`; the trash toggle
  calls `listOrders` with `trash: true` and puts `trash=true` in the URL; a row shows days left;
  row restore and row delete call the API and reload; error paths — a rejected call with code
  `ORDER_NOT_IN_TRASH` / `ORDER_IN_TRASH` (409) and a network failure — show the message and
  leave the buttons enabled. Frontend gate green and the full backend gate green (backend tests
  read `frontend/src`).

- [x] **T23 · Live SQL for migration 0015 → 0016**
  owner: backend-dev
  files: docs/migrations/0016_orders_deleted_at.sql (new)
  depends: T18
  What: from `backend/`, offline (connects to nothing):
  `VOLTBOX_NO_DOTENV=1 JWT_SECRET=<any 32+ characters> DATABASE_URL=postgresql://voltbox:voltbox@localhost:55432/voltbox .venv/Scripts/alembic.exe upgrade 0015:0016 --sql`
  (`alembic/env.py` imports `settings`, which needs `DATABASE_URL` and a `JWT_SECRET` of at
  least 32 characters when `.env` is off — T17). Every table name hand-qualified `public.`
  (`public.orders`, `public.alembic_version`; Supabase has its own `auth.*` tables).
  done when: the file holds that output, qualified, with a header comment: how it was generated
  and from which commit; the statement count between `BEGIN` and `COMMIT` (expected 3: add
  column, create index, the `alembic_version` update — which checks `version_num = '0015'`, so
  look for `UPDATE 1`); the checks to run after (`select version_num from public.alembic_version;`
  → `0016`; `select data_type, is_nullable from information_schema.columns where table_schema='public'
  and table_name='orders' and column_name='deleted_at';` → `timestamp with time zone`, `YES`).
  Applied to a scratch local database at `0015` (inside the compose `db` container, never live;
  no host psql is needed), it leaves `alembic current` = `0016` and `alembic check` clean.
  No backend file changes, so no gate beyond `git diff --stat` showing only this file.

### Deploy plan — Stage 2 (to finish once T18–T23 are done; nothing here is run from the agent side)
1. **Migration on live** — the owner pastes `docs/migrations/0016_orders_deleted_at.sql` into the
   Supabase SQL editor (live head is `0015`). Additive: a nullable column and an index; the old
   backend never reads it. The new backend reads `deleted_at` in every order query, so it must
   exist first.
2. **Backend** (`voltbox-api`).
3. **Frontend** (`voltbox-storefront`). The old admin with the new backend works (trashed orders
   are just hidden); the new admin with the old backend gets errors on the trash buttons. One
   push to `main` starts both services and the static site usually finishes first (Stage 1 record
   below) — a few minutes in which the trash buttons fail; no shopper-facing change.
- Environment variables: none new, none changed.
- After the deploy (by hand, on a test order the owner places for it, never a real one): trash it
  → gone from the list and the dashboard, in "სანაგვე" with a purge date → restore → back with the
  same status; trash again → "სამუდამოდ წაშლა" → gone; the product's stock is the same before and
  after (it dropped once, at checkout).

## Shared files
<!-- Files that may appear in several tasks' files as (shared). Rule: append only (new dependency, type, route); never change or remove someone else's entry; two tasks never work on one shared file at the same time. -->
- None. `frontend/src/i18n/ka.json` and `en.json` appear in T19 and T20 only, and T20 depends on
  T19, so the two never run at the same time. `backend/app/services/order_trash.py` and
  `backend/app/api/v1/routes/admin/orders.py` likewise (T19 → T20).

## Backlog (needs user decision)

- Design nits from DESIGN.md (2026-10-18, designer): admin palette misses AA on ink-500/ink-100 (4.37),
  danger-fg/danger-50 (4.41) and control border ink-300/white (1.66); admin uses accent (orange) as its main
  colour while the palette says accent is for prices; four focus styles; two badge systems; raw `rounded-lg`/
  `text-[11px]` instead of tokens; admin has no mobile navigation below `md` (low).

- **Stage 2 — two proposed Accepted Risks** (PROJECT.md → Accepted Risks): a permanently deleted
  order is gone (only the audit row remains), and deleting never returns stock. Owner to confirm.

- **City names in English** (owner, 2026-10-14: after sales start). `GET /delivery` and the checkout
  city list send Georgian names, so `/en` shows `თბილისი` in the delivery table and the city field.
  Needs the backend to send names by `lang` (like the catalogue). `SHOP_FACTS` values have the same
  limit - one language each.

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

Deploy plan — **DONE 2026-10-10**: the owner deployed `d25910e` (voltbox-api and voltbox-storefront) and
ran `0015` on live by hand (head = 0015; `carts` and `alembic_version` have RLS). Kept below as the record.
Nothing in it was run from here — no alembic, no SQL, no push, no Render call.
Prepared 2026-10-10 for Stage 1 (code at `7a867fb`).

**1. Migrations on the live Supabase database**
- Stage 1 added exactly one migration: `0015` (RLS on `public.carts` and `public.alembic_version`).
  Live already shows RLS on 15/15 tables (advisor, owner), so on live it changes nothing but the
  recorded head. The backend works the same without it; run it so live and `alembic upgrade head`
  agree and a rebuilt database matches.
- **Live head is 0014** (owner confirmed 2026-10-10). Only the last block, `0014 -> 0015`, is left to run.
  Its last `UPDATE` checks the old value, so on a wrong head it updates 0 rows — look for `UPDATE 1`.
  The 0010–0014 blocks are kept below as reference only; do not run them.
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
- 0010–0014 predate Stage 1 and are already applied on live.

**2. Order**
1. Migrations (additive or no-ops for running code: new columns have defaults, RLS with no policy does not
   affect the backend role) — before any code that reads `lookup_token_hash`, `name_en` or `password_reset_tokens`.
2. Backend (`voltbox-api`).
3. Frontend (`voltbox-storefront`).
Why backend first: the new storefront sends `currentPassword` and caps lines at 10 units; the old API would
reject the unknown `currentPassword` field (email change fails), while the new API with the old storefront
refuses only an email change without a password and a cart line over 10. Either order has a window of a few
minutes; backend-first keeps browsing and checkout working in it.
Decided by the owner (2026-10-10): the storefront's auto-deploy stays on. `render.yaml` has no `autoDeploy`
key, so one push to `main` starts both services (each has its own `buildFilter`) and the static site usually
finishes first; the short window is accepted because there are no real shoppers yet. Nothing is pushed from here.

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
   On onrender.com the session still ends after 30 minutes (Accepted Risk) — expected.  ✅ login (owner, 2026-10-10); cookie not reported
3. Guest order with one product × 10 → created; × 11 → refused; a 21st different product in the cart →
   the "at most 20 different products" message. The new order shows a started status timeline in the admin (T10).  ✅ cart limit 10 with the Georgian message, and an order placed (owner); 11/21 refusal at the API and the timeline not reported
4. Signed-in checkout, repeated with the same Idempotency-Key (double click / retry) → no error page.
5. Profile: change email without the current password → refused; with it → works.
6. Admin: upload a photo over 5 MB → "photo is over 5 MB" (T13); a normal photo → saved.
7. Admin: rename a brand → its products are found by the new name in search (T9).  ✅ (owner)
8. Rate limit: the 6th order within a minute from one IP → 429 (use a test product and delete the test
   orders by hand in the admin afterwards).
9. Supabase Dashboard → Advisors: no new "RLS disabled" warning.
   ✅ for the two tables (owner: RLS = true on `carts` and `alembic_version`); the advisor page itself not reported.
Not yet reported (⬜ do when convenient): 1 health, 4 signed-in duplicate checkout, 5 email change, 6 photo over
5 MB, 8 rate limit. **D2 (section 4) is still open** — the Data API step is for before the public launch.

Nits:
- Tailwind 4-ზე გადასვლისას postcss-selector-parser და dev-ჯაჭვის high-ები თავისით გასწორდება.
  Dependabot, owner dismisses all three, 2026-10-10 (build-time only): #17 source-map-js (high),
  #16 postcss-selector-parser 6.1.4 < 7.1.6 (moderate), #12 brace-expansion (moderate) — all dev,
  `frontend/package-lock.json`. `tailwindcss` is a devDependency, runs only in `npm run build` on our
  own CSS and is not in `dist`; CI's `npm audit --omit=dev --audit-level=high` does not see them.
  `npm audit` also lists braces, micromatch, chokidar, fast-glob and tailwindcss 3 (high, same chain).
  Not fixed with an `overrides` entry on purpose.
  Correction: an earlier note here named #12 as postcss-selector-parser and said backend `pip-audit` was
  clean; #12 is brace-expansion, and Mako (#13, #14) was in the backend locks — pip-audit missed it.
  Mako is fixed (1.4.1 -> 1.4.3 in `requirements.txt` and `requirements-dev.txt`).
- pip-ის პაკეტების ეტაპობრივი განახლება --upgrade-package-ით (fastapi, starlette, sqlalchemy 2.1 ცალკე).
  The Dependabot pip group (16 packages) was closed, 2026-10-10: its lock bumped `pydantic-core` to 2.49.0
  while pydantic 2.13.5 pins `pydantic-core==2.46.5`, and `sqlalchemy` 2.0 -> 2.1 is a minor on a core
  dependency. Do it in the Linux container (backend/README.md), one package or one family per commit.
- React 19 — როცა საჭირო გახდება, ერთად react + react-dom (და ორივე @types). The two Dependabot
  PRs were closed, 2026-10-10: react 19 with react-dom 18 does not work, so they cannot merge one by one.
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
- `frontend/README.md:453-455` still says the four info pages are Georgian in both languages and built with
  `lang="ka"` / `tKa`; T16 removed both. Only city names and `SHOP_FACTS` values stay Georgian (2026-10-14).

Unverified (check before acting):
- `FORWARDED_ALLOW_IPS` value on Render — if wrong, all clients share one bucket.
- Render health check vs the 60/min default limit (429 restart loop?).
- Redis client has no socket timeouts (a blackholed Redis could stall a worker).
- Supabase session-pooler size vs the 30-connection budget.
- Render edge body-size limit; multipart image body parsed before `require_admin`.
- Two concurrent first-image uploads → 500 + orphaned file.
- A 6–8 MB photo refused early by `body_limit._refuse` (413 + `connection: close` while the browser is still
  sending) may reach the panel as a connection reset, i.e. `apiErrors.network`, not "photo is over 5 MB". From T8;
  not reproducible locally. Deploy checklist item 6 (photo over 5 MB on live) answers it.

## Blockers
- None.

## Run State
- Stage: Stage 2 — Order trash (admin)
- Finish-check this stage: not run
- Fix rounds this stage: 0/2
- Failed attempts: —

## Last Session
- Date: 2026-10-18
- Done: planned Stage 2 (order trash): PROJECT.md (scope, Business Rules → Order trash, Data, API
  Contract, Decision Log, two proposed Accepted Risks, assumptions under Open Questions) and this
  file (T18–T23). Nothing implemented.
- Verification: none run — planning only; no code, database or git state changed.
- Known issues / blockers: the two proposed Accepted Risks wait for the owner.
- Next: T18; then T19, T21 and T23 in parallel; T20; T22.

## Stage 1 — Done
Stage 1 — Audit fixes (closed by the owner 2026-10-10; T0–T17 done)

Source: full audit 2026-10-10 (standard-reviewer, three slices: auth/authz/privacy;
money/stock/data/Supabase; frontend/config/CI/Docker). Every task below was
re-checked in the code before it was written here. Order = suggested order.

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

- [x] **T15 · should-fix · The live footer says "demo project — data from a mock source".**
  `Footer.jsx` rendered `t('footer.demo')` in every mode, so the http build on Render (which
  `frontend/render.yaml` pins to `VITE_API_MODE=http`) told shoppers the data was mock.
  Fix: the notice renders only when `VITE_API_MODE !== 'http'` (same check as `routes.jsx`);
  the text stays in `ka.json` and `en.json` for mock. Tests: shown in mock, absent in http.
  Check: the http `dist` has no `footer.demo` call (the sentence itself stays in the bundled
  dictionary, so grepping the text proves nothing); the mock `dist` has it. Live shows the change
  only after the owner redeploys the storefront.
  **Done 2026-10-14:** `3268c71` is live and the owner checked in the browser that the footer notice is
  gone (so the Render build is http). Backend `pytest -q` was not run for this change: Docker was
  unreachable from the agent's shell (1009 errors, all DB connect). ruff, format and mypy are green;
  the change touches only `Footer.jsx` and its test.

- [x] **T16 · should-fix · The info pages (/delivery, /returns, /privacy, /faq) have an English title and a Georgian body.**
  Their text was written into the components and `InfoPage.jsx` wrapped it in `lang="ka"`;
  `i18n.test.js` skipped the six files. There is no separate "terms" page (the owner decides that later).
  Fix: the text moved to `info.*` in `ka.json` (word for word) with the English in `en.json`; pages use
  `t()` / `<Rich>`; `lang="ka"` and `tKa` are gone; the six files are no longer skipped by the
  "no Georgian in components" test. Delivery wording (where, cost note, time, payment, receipt, table)
  is all under `info.delivery`, the time is `shipping.etaDays`: a courier change is edited there only.
  Privacy and Returns English follows the Georgian sentence for sentence.
  Check: the old and the new Georgian HTML of the four pages, 16 variants (owner facts set/unset x email
  on/off), compared byte for byte: identical. Frontend lint, vitest (580), both builds and backend
  ruff, format, mypy, pytest (1009) green. New English tests: no Georgian in any page (text, aria,
  caption, meta description), the table, links, owner facts.
  Not translated on purpose: city names (`GET /delivery`, see Backlog) and the `SHOP_FACTS` values
  (`returnPickup`, `warrantyPeriod`, `legalEntity`), which the owner writes in one language: on
  `/en` they would appear as written.

- [x] **T17 · should-fix · `scripts/verify_restore.py` still loads `backend/.env`, and its localhost guard has two gaps.**
  Found by the 2026-10-14 finish-check (scope `cff0b34..HEAD`); T14's claim "never reads backend/.env" is not true.
  `verify_restore.py:38` imports `app.db.ssl` → `app/core/config.py:331` `settings = get_settings()`, which reads
  `.env` from the cwd. `docs/backup-restore.md:143` runs the script from `backend/`, so the live `DATABASE_URL` and
  every key are loaded into the process (no connection to live: `--against` is local, and `build_connect_args` is
  used only for a `supabase` URL). With `VOLTBOX_NO_DOTENV=1` the import fails instead (`jwt_secret` required), so
  the documented command works only by loading the live `.env`. `test_the_module_does_not_read_a_dotenv` cannot see
  it: pytest already sets the flag and has imported `app.core.config`.
  Reproduced from a scratch cwd with a sentinel `.env` (never `backend/.env`): without the flag `settings.db_ssl_mode`
  came from the sentinel.
  Same guarantee, same file: (a) the positional `restored` URL is not checked at all; (b) `is_local` uses `urlsplit`,
  but SQLAlchemy's asyncpg dialect passes `url.query` to connect, so
  `postgresql://u:p@localhost:5432/db?host=db.x.supabase.co` passes `is_local` and connects to `db.x.supabase.co`
  (checked with `create_connect_args`, no network).
  Done when: the script no longer imports `app.*` settings (drop `app.db.ssl` and the `"supabase" in url` branch -
  both URLs are local, no TLS); a subprocess test from a cwd holding a sentinel `.env`, with `VOLTBOX_NO_DOTENV`
  and `JWT_SECRET` unset, shows the script runs to its argument check without loading it; both URLs are checked
  with `make_url`, host in `LOCAL_HOSTS` and no `host`/`hostaddr` in the query (tests for `restored` remote and for
  `?host=`); the docstring and `docs/backup-restore.md` say what holds.
  **Done 2026-10-14:** the script imports nothing from `app`; `is_local` uses `make_url` and rejects `host`/`hostaddr`
  in the query; both URLs are checked. Checked by hand from a scratch cwd with a sentinel `.env`, flag and
  `JWT_SECRET` unset: remote `restored` and `?host=` on `--against` both exit 2. Not run: the new tests against the
  old code (reasoned only); the subprocess test only on Windows, not on Linux CI.

Stage 1's last Run State and Last Session, kept as the record:
- Finish-check this stage: done (2026-10-10); second run 2026-10-14 over `cff0b34..HEAD` (T13–T16, deps) → T17
- Fix rounds this stage: 1/2
- Failed attempts: —
- 2026-10-14 finish-check over `cff0b34..HEAD`: ruff, format, mypy, pytest 1009; frontend lint, vitest 580, both
  builds (http `dist` has no `footer.demo` call, mock has it) - all green. T17 (should-fix) found and fixed the same day: pytest 1017, ruff, format, mypy green. No stage is open; the finish-check can be re-run.
- Date: 2026-10-10
- Stage 1 closed and **deployed** (`d25910e`, owner). Dependabot: Mako #13/#14 closed by the fix;
  #12/#16/#17 dismissed (build-time only); the pip group, react and react-dom PRs closed by the owner; the npm
  minor/patch and the Docker digest are in `f09dab4` / `bd9cf63` (their PRs are superseded).
- Done: T13 (oversized photo says IMAGE_TOO_LARGE), T14 (verify_restore never reads `.env`; `--against` required, localhost only — owner approved).
- Verification: ruff, format, mypy, pytest 1009 — green, run by orchestrator. Frontend untouched since T12 (vitest 566, builds green).
- Known issues / blockers: executor ran the OLD verify_restore.py from backend/ to prove the new tests fail, so `backend/.env` was loaded into that one test process (nothing printed or sent; one failed localhost:55433 connect). Owner told.
- Next: no stage is open. The owner picks the next one (Backlog nits, D2 before launch, `voltbox.ge` list).
