# VoltBox

> This file holds requirements, scope and the decisions made from now on.
> Every technical decision taken before 2026-10-10, with its reason, is in
> [ASSUMPTIONS.md](./ASSUMPTIONS.md) (§1–§10) and is not repeated here. What was
> deliberately postponed is in [ROADMAP.md](./ROADMAP.md); what is left before
> launch is in [TODO.md](./TODO.md); deployment in [docs/deployment.md](./docs/deployment.md).

## Overview
Online store for electronics and accessories (phones, cables, power banks,
chargers, headphones, accessories) in Georgia. Storefront in Georgian (default,
unprefixed URLs) and English (`/en/...`); admin panel in Georgian only.
Currency GEL (₾).

## Users
- **Guest** — browses, searches, keeps a cart in the browser, checks out without
  an account; reads their own order only with the random `lookupToken` returned
  at checkout (ASSUMPTIONS §8.5).
- **Customer** (`role = customer`) — registers with email + password; profile,
  saved addresses, order history, a server-side cart that follows them between
  devices, password change and password reset by email.
- **Admin** (`role = admin`) — catalog (categories, brands, products, images),
  stock adjustments, order status, customers, dashboard. Created and promoted
  only from the CLI (`scripts/manage_admin.py`); public registration cannot set
  a role.
- **Owner** — receives a Telegram notice for every new order (optional config).

## Current Stage
Stage 2 — Order trash (admin) (planned 2026-10-18; tasks in PROGRESS.md).
Stage 1 — Audit fixes is closed and deployed (`d25910e`, live head `0015`).

Deployment state, as far as the repository shows (2026-10-10):
- Render, free plan, onrender.com addresses, no domain yet (`voltbox.ge` not
  bought — TODO.md §1). API `voltbox-api` and storefront `voltbox-storefront`
  are defined as Blueprints (`backend/render.yaml`, `frontend/render.yaml`).
  docs/deployment.md §0 says the storefront was not created yet when it was
  written; the current state on Render is not recorded in the repo.
- Database: live Supabase PostgreSQL 17 (eu-central-1). It holds real data the
  owner entered — their admin account, categories, brands and products.
  **Treat it as production.** Nothing there is disposable.
- Signs that there are no real customers yet: no domain, outgoing email off
  until the domain exists, free instance that sleeps after 15 minutes,
  TODO.md "🔴 გაშვებამდე აუცილებელი" still open. Not provable from the code —
  see Open Questions.

## Scope
### In scope (current stage)
- Order trash in the admin panel (owner's request, 2026-10-18): deleting an order moves it
  to a trash (after a confirmation dialog); one-click restore from the trash; permanent
  deletion by hand, or automatically 30 days after it was trashed. Admin only. Deleting
  never changes stock. Rules: Business Rules → "Order trash"; endpoints: API Contract.
- Keep the existing behaviour, stack and conventions.

### Out of scope (for now)
- Bulk delete / bulk restore (one order at a time).
- Customer- or guest-side order deletion.
- A cron job or scheduled task for the 30-day purge (no cron on the Render free plan;
  the purge runs lazily — Decision Log 2026-10-18).
- Online payment (cash on delivery only — ASSUMPTIONS §4.6).
- Delivery outside Tbilisi and Rustavi (ASSUMPTIONS §4.5).
- New features from ROADMAP P2/P3 (wishlist, reviews UI, promo codes, ...).
- Migrating stack, ORM, router or styling.

## Core Flows
1. Browse catalogue → filter / search (server-side, facets) → product page.
2. Cart in the browser; for a signed-in customer also saved on the server.
3. Checkout (guest or customer) → `POST /orders` with a mandatory
   `Idempotency-Key` → server prices every line from the database, decrements
   stock, writes inventory movements and the timeline's first row (`pending →
   pending`, as migration 0004 did for older orders) in one transaction → order
   number `VB-...`; Telegram notice to the owner; email confirmation when email
   is configured.
4. Admin moves the order through the status machine; cancellation returns stock.
   Admin trash (Stage 2): order detail → "წაშლა" → confirmation → the order is in the
   trash (`deleted_at` set) and hidden everywhere else → "აღდგენა" brings it back as it
   was, or "სამუდამოდ წაშლა" / the 30-day purge removes it for good.
5. Auth: register / login (Argon2, account lockout) → short-lived access JWT +
   rotating refresh token in an httpOnly cookie (family reuse detection) →
   logout / revoke-all on password change or admin block. Password reset by
   one-time emailed link (off until email is configured).

## Business Rules
- **Prices and totals are computed only on the server**, from the database;
  the client never sends a price (`extra="forbid"` — ASSUMPTIONS §8.6). Money is
  `Numeric`/`Decimal`, never float.
- **Delivery fee** by city: Tbilisi 8 ₾, Rustavi 5 ₾, free when the items total
  is ≥ 50 ₾; other cities are refused (`app/services/delivery.py`).
- **Payment**: cash on delivery only for new orders; old `card` orders still load.
- **Order size** (decided 2026-10-10): at most 20 distinct products per order and 10 units
  of each. One source: `app/core/limits.py`; the cart has the same caps; the storefront copy is
  in `frontend/src/constants/index.js`.
- **Stock** never goes negative; every change writes an `inventory_movements`
  row (previous, change, new). Checkout and cancellation are the automatic
  writers; admins adjust with a reason.
- **Order status machine** (`app/services/order_status.py`):
  `pending → confirmed → processing → shipped → delivered`; `cancelled` from
  pending/confirmed/processing; `delivered` and `cancelled` are terminal.
  Every transition writes `order_status_history` in the same transaction.
- **Ownership**: a customer reads and changes only their own orders, addresses,
  cart and profile; a guest only the order whose lookup token they hold.
- **Admin** checks read the role from the database on every request, not from the JWT.
- **Idempotency**: `POST /orders` requires `Idempotency-Key`; a replay returns
  the same order and does not decrement stock twice (ASSUMPTIONS §8.14).
- **Order trash** (Stage 2, decided 2026-10-18):
  - Only an admin trashes, restores or permanently deletes (router-level `require_admin`,
    role read from the database). One order at a time.
  - A trashed order (`orders.deleted_at IS NOT NULL`) is visible only in the admin trash
    (`GET /admin/orders?trash=true`) and on the admin order detail page. It is hidden from:
    the admin default order list, `counts_by_status`, the dashboard (sales today/total,
    orders today, top products, latest orders), the admin customers' order count, spend
    and order list, the customer's own list and `GET /orders/{number}`, and the guest
    lookup — which answers 404 `ORDER_NOT_FOUND`, exactly as for a missing order.
  - An idempotent replay of `POST /orders` whose order is trashed still returns that order
    and creates nothing: never a second order, never a second stock decrement. (Once the
    order is purged its key is gone with it; a replay arriving after that would place a new
    order — 30+ days after checkout, not a realistic retry.)
  - **Stock is never touched** by trash, restore or purge: no `adjust_stock` call, no
    `inventory_movements` row written or deleted. Purge leaves the ledger rows in place with
    `order_id` set to NULL (FK `ON DELETE SET NULL`). Trashing a pending, confirmed or
    processing order keeps its units out of stock; the confirmation dialog says so and tells
    the admin to cancel first if the units should come back. No restriction by status.
  - **Status is frozen while trashed**: `order_status.transition` refuses it with 409
    `ORDER_IN_TRASH` (checked after the row lock); the detail returns
    `allowedTransitions: []`. Restore returns the order to the status it had, unchanged.
  - **Retention**: 30 days from `deleted_at`, one constant in one place
    (`services/order_trash.py`). Trashing an order already in the trash keeps its original
    `deleted_at`; restore then trash again starts a new 30 days. The purge runs at the
    start of `GET /admin/orders`, so an expired order disappears the next time the order
    list is opened; `purgeAt` is when it becomes eligible, not a promise of the exact minute.
  - **Permanent delete** (by hand or automatic) removes the order, its items and status
    history (CASCADE). The `admin_audit_log` row (`order.purge`) is the only record left
    (Accepted Risks → proposed).
  - A product that appears only in trashed orders still cannot be deleted
    (409 `PRODUCT_IN_USE`, unchanged) until those orders are purged.

## Data
PostgreSQL, Alembic migrations `backend/alembic/versions/0001`–`0016` (`0016` = Stage 2,
`orders.deleted_at`; live is at `0015` until the owner runs the 0016 SQL).
- Catalogue: `categories` (tree, `filters` config), `brands`, `products`
  (price, old price, stock, specs JSONB, `search_text`, `name_en`,
  `archived_at`), `product_images`.
- Customers: `users` (role, token_version, lockout counters), `addresses`,
  `carts` (one JSONB cart per account), `refresh_tokens` (families),
  `password_reset_tokens` (one per account, SHA-256 only).
- Orders: `orders` (snapshot of contact and delivery, totals, idempotency key,
  guest `lookup_token_hash`, `deleted_at` — NULL = live, set = in the trash; partial index
  `ix_orders_deleted_at ... WHERE deleted_at IS NOT NULL`, declared in the model too so
  `alembic check` stays clean), `order_items` (price and name snapshot),
  `order_status_history` (both CASCADE with the order).
- Audit: `inventory_movements`, `admin_audit_log` — no retention (ASSUMPTIONS §8.15).
- Retention: `refresh_tokens` pruned 7 days after expiry by
  `scripts/prune_refresh_tokens.py` (cron job removed while on the free plan).
  Trashed orders: hard-deleted 30 days after `deleted_at` (Business Rules → Order trash).

## API Contract
This section is the contract between frontend and backend for **the endpoints added or
changed in Stage 2**. Every other endpoint is defined by its route module under
`backend/app/api/v1/routes/` and FastAPI's OpenAPI schema, and is unchanged.

Common to all API endpoints (existing, unchanged):
- Base path `/api/v1`. JSON keys are camelCase (`schemas/base.py`); money is a decimal
  string (`"125.00"`); timestamps are ISO 8601 with timezone (UTC).
- **One error format** (`core/errors.py`), every 4xx/5xx:
  `{"error": {"code": "<STABLE_CODE>", "message": "<English, for logs>", "details": <object | array | null>}}`.
  The UI shows the text for `code` from `frontend/src/i18n/ka.json` → `apiErrors.<CODE>`.
  Validation errors are 400 (never 422).
- Every `/admin/*` endpoint: `Authorization: Bearer <access JWT>`; 401 `INVALID_TOKEN`
  without a valid token, 403 `ADMIN_REQUIRED` for a non-admin (role read from the DB).
  A path `{id}` that is not a UUID → 400 `VALIDATION_ERROR`.

Shapes used below:
- `OrderListItem` (existing fields + two new ones): `id` uuid, `orderNumber` string,
  `status` string (`pending|confirmed|processing|shipped|delivered|cancelled`),
  `customerName` string, `phone` string|null, `email` string|null, `city` string|null,
  `total` decimal string, `itemCount` int, `paymentMethod` string, `createdAt` datetime,
  **`deletedAt` datetime|null** (null = live order), **`purgeAt` datetime|null**
  (`deletedAt` + 30 days; null for a live order).
- `OrderDetailOut` = `OrderListItem` + `customer` object, `shippingAddress` object,
  `subtotal` decimal string, `shipping` decimal string, `currency` string, `notes`
  string|null, `items` [`{id, productId, productName, productSlug, imageUrl, unitPrice,
  quantity, lineTotal}`], `allowedTransitions` string[] (**`[]` while the order is
  trashed**), `history` [`{fromStatus, toStatus, changedBy, note, createdAt}`].
- `OrderPage`: `{items: OrderListItem[], total: int, page: int, totalPages: int, limit: int}`.

| Method | Path | Request | Success | Errors |
|---|---|---|---|---|
| GET | `/admin/orders` | query: `page` int ≥1 (1), `limit` int 1..max (default page size), `q`, `status`, `dateFrom`, `dateTo` (YYYY-MM-DD) — as today; **new** `trash` bool (default `false`) | 200 `OrderPage`. `trash=false`: live orders only, newest `createdAt` first. `trash=true`: trashed orders only, newest `deletedAt` first; the other filters apply the same way | 400 `INVALID_DATE`, 400 `VALIDATION_ERROR` (bad `page`/`limit`/`trash`) |
| GET | `/admin/orders/{id}` | — | 200 `OrderDetailOut` — live **or trashed** | 404 `ORDER_NOT_FOUND` |
| POST | `/admin/orders/{id}/status` | `{to: string, note?: string\|null}` — unchanged | 200 `OrderDetailOut` | 400 `UNKNOWN_STATUS`, 404 `ORDER_NOT_FOUND`, 409 `INVALID_TRANSITION`, **409 `ORDER_IN_TRASH`** (order is trashed; nothing changes) |
| POST | `/admin/orders/{id}/trash` | no body | 200 `OrderDetailOut` with `deletedAt`/`purgeAt` set. Idempotent: an order already in the trash → the same response, `deletedAt` unchanged, no new audit row | 404 `ORDER_NOT_FOUND` |
| POST | `/admin/orders/{id}/restore` | no body | 200 `OrderDetailOut` with `deletedAt`/`purgeAt` null, `status` as before the trash. Idempotent: a live order → the same response, no audit row | 404 `ORDER_NOT_FOUND` (also when it was purged meanwhile) |
| DELETE | `/admin/orders/{id}` | no body | 204, empty body. Order, its items and status history are gone; stock and `inventory_movements` rows unchanged (their `order_id` becomes NULL) | 404 `ORDER_NOT_FOUND`, **409 `ORDER_NOT_IN_TRASH`** (a live order; trash it first) |

Side effects:
- `GET /admin/orders` (both modes) first purges every order whose `deletedAt` is more than
  30 days old, in its own committed transaction, then runs the list query.
- Audit rows (`admin_audit_log`, same transaction as the change; `entity_type = "order"`,
  `entity_id` = order id):
  `order.trash` (actor = admin, `changes: {status, deletedAt}`),
  `order.restore` (actor = admin, `changes: {status, deletedAt: null}`),
  `order.purge` (`changes: {orderNumber, status, total, automatic: bool}`; actor = admin for
  `DELETE`, `NULL` with `automatic: true` for the 30-day purge). No customer name, phone or
  address goes into the audit row.
- New error codes `ORDER_IN_TRASH` and `ORDER_NOT_IN_TRASH` have Georgian and English text
  under `apiErrors` in `frontend/src/i18n/ka.json` and `en.json`
  (`backend/tests/test_error_messages.py` enforces the Georgian one; `i18n.test.js` key parity).

## Integrations
- **Supabase** — PostgreSQL (session pooler) and Storage (`product-images`,
  public bucket, written only by the backend with the service-role key).
  The database is backend-only: no browser talks to it; RLS is enabled with no
  policies as a safety net (ASSUMPTIONS §8.7).
- **Redis** — shared rate-limit counters across gunicorn workers (`REDIS_URL`);
  falls back to per-process counters if Redis is down.
- **Telegram Bot API** — new-order notice to the owner (optional).
- **Resend** — order confirmation and password-reset email (off until the domain).
- **Render** — hosting for the API (Docker) and the storefront (static site).

## Stack & Architecture
- Complexity tier: Tier 2 — Standard (one backend, one database, real money
  and stock, admin panel, no queues or microservices).
- Frontend: React 18 SPA, Vite 8, Tailwind 3, React Router 7 (library mode),
  i18next; `services/api.js` contract with mock/http implementations chosen at
  build time (ASSUMPTIONS §6.1).
- Backend: Python 3.14, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic,
  Pydantic 2, PyJWT, argon2-cffi, slowapi/limits, gunicorn + uvicorn workers.
- Database: PostgreSQL 17 (Supabase in production, Docker locally/CI).
- Storage: Supabase Storage.
- Auth: own JWT access tokens + rotating refresh tokens (httpOnly cookie).
- Hosting / deployment: Render Blueprints (Frankfurt), CI on GitHub Actions.

## Realistic Scale
Small single-shop store at launch: tens to low hundreds of visitors a day,
a handful of orders a day, hundreds of products, one or two admins.
Connection budget `workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW) ≤ 30`.

## Security & Privacy
- Personal data: customer name, phone, email, delivery address, order history;
  admin audit log stores IP. No card data is ever handled.
- Secrets only in `backend/.env` (never read or committed) and Render env;
  `SUPABASE_SERVICE_ROLE_KEY` backend-only.
- Rate limits per client IP (`app/core/rate_limit.py`): auth 5/min (incl. password
  change and profile update), `POST /orders` 5/min and 30/day, guest order lookup
  10/min, client error reports 20/min, guest cart quote (`POST /cart/quote`) 30/min,
  everything else 60/min; password reset also 3/hour per email address. Redis-backed in production; client IP
  only through `FORWARDED_ALLOW_IPS` (never `*`).
- Production startup refuses unsafe config (CORS `*`, missing
  `TRUSTED_HOSTS`/`FORWARDED_ALLOW_IPS`, short `JWT_SECRET`, ...).
- Every new table must enable RLS in its migration — the Supabase API is
  public, and a table without RLS is readable through it with the anon key.
- Order trash (Stage 2): trash/restore/delete are admin-only through the router-level
  `require_admin` (`tests/test_admin_auth.py` enumerates every admin route). A trashed
  order must not be readable by its customer or a guest token holder, and the guest lookup
  must not tell "trashed" from "missing" (same 404 — order numbers are sequential).
  A purge removes the order's personal data for good; its audit row keeps only order
  number, status, total and who/when.

## Accepted Risks
- **Sessions last 30 minutes on onrender.com** (owner, 2026-10-10). Storefront and API are
  different sites there (`onrender.com` is on the Public Suffix List), so the
  `SameSite=strict` refresh cookie cannot cross; admin and customers sign in again after
  30 minutes. Ends with `voltbox.ge` + `api.voltbox.ge`. Not accepted: logout failing to
  revoke or reuse detection not persisting — those are T1/T3.
- **Proposed, owner to confirm (Stage 2) — a permanently deleted order is gone.** "სამუდამოდ
  წაშლა" or the 30-day purge removes the order, its items and its status timeline; there
  is no restore, and sales totals, top products, customer spend and the dashboard lose it.
  The `admin_audit_log` row (`order.purge`: order number, status, total, who, when,
  automatic or not) is the only record. Not accepted by this proposal: losing anything
  while the order is only in the trash — restore must bring it back unchanged.
- **Proposed, owner to confirm (Stage 2) — deleting never returns stock** (the owner's rule;
  this records its consequence). An order trashed
  or purged while pending, confirmed or processing keeps its units out of stock for good;
  the admin must cancel it first (cancellation returns stock) or adjust stock by hand. The
  confirmation dialog says this. What still holds: the stock ledger is never edited, so
  `inventory_movements` still adds up to the product's stock.

## Constraints
- Budget: free tiers until launch (Render free, Supabase free — no scheduled
  backups, TODO.md §5).
- One developer + AI agents. Work on branch `agent-system`; push and merge to
  `main` only with the owner's approval.
- Never against the live database from an agent: `alembic upgrade/downgrade`,
  `seed.py`, `import_products.py`. Migrations reach Supabase as reviewed,
  schema-qualified SQL the owner pastes into the SQL editor.
- No deploys from agents. `backend/.env` is not read or edited.
- Dev on Windows; CI and production on Linux (Python 3.14, Node 22).

## Decision Log
Decisions before 2026-10-10: [ASSUMPTIONS.md](./ASSUMPTIONS.md).

### 2026-10-18 — `deleted_at` is written from the application clock (T19)
- Decision: `order_trash.trash` sets `deleted_at = datetime.now(UTC)`; `purgeAt` is that value
  plus `TRASH_RETENTION`, and the 30-day purge (T20) compares against a cutoff taken from the
  same application clock, so one clock decides both.
- Reason: the database's `now()` is frozen at the start of the transaction, so two trashes in
  one transaction would share an instant and "newest deletion first" could not be tested.
- Alternatives considered: `func.now()` (database clock).
- Why rejected: the frozen-instant problem above; app and database run in UTC on the same
  host class, so a skew of seconds against a 30-day retention does not matter.

### 2026-10-18 — No `@playwright/test` setup task for Stage 2; browser checks use the existing `playwright`
- Decision: the stage gets no "Browser testing setup" task. The repo already drives a real
  browser with the `playwright` library (`frontend/package.json` devDependency 1.63.0,
  `frontend/scripts/e2e/cart-sync.mjs`); browser checks of the admin trash use that.
- Reason: adding `@playwright/test` rewrites `frontend/package-lock.json`, and a lock written
  with the local Node 24 / npm 11 has turned CI (Node 20 / npm 10) red before. The admin is
  http-only, so a mock-mode smoke test would not reach the trash UI anyway.
- Alternatives considered: `@playwright/test` + `playwright.config.*` + an `e2e/` smoke test.
- Why rejected: a new dependency and a lock change for a check the existing library can do.
  Revisit if the project wants browser tests in CI.

### 2026-10-18 — Stage 2 stays Tier 2, no new layer or dependency
- Decision: the order trash is one nullable column, one service module
  (`services/order_trash.py`), four route changes on the existing admin orders router and
  two admin pages; no new table, library, job runner or frontend state library.
- Reason: one or two admins and a handful of orders a day; every requirement (hide,
  restore, purge after 30 days, audit) fits the existing FastAPI + SQLAlchemy + React stack.
- Alternatives considered: a generic soft-delete mixin / global query filter for all models.
- Why rejected: only orders need it; a global filter hides rows from code that must see
  them (idempotency replay, admin detail, purge) and makes every query's meaning implicit.

### 2026-10-18 — Admin UI for the trash: buttons on the detail page, a trash view on the list
- Decision: OrderDetail gets "წაშლა" → `ConfirmDialog` (with the stock warning for
  pending/confirmed/processing) → trash → back to `/admin/orders` with a success toast
  (existing `useToast`). A trashed order's detail shows a banner with the purge date, hides
  the status buttons, and offers "აღდგენა" (one click, no dialog) and "სამუდამოდ წაშლა"
  (`ConfirmDialog`). OrderList gets a "სანაგვე" toggle (`?trash=true` in the URL like the
  other filters) with deletion date, days left, and per-row restore and permanent delete
  (`ConfirmDialog`). `adminApi.js` gets `trashOrder`, `restoreOrder`, `deleteOrderForever`
  and the `trash` param. Errors show through the existing `apiErrors` lookup. Admin text is
  Georgian in the components, as in the rest of `src/admin` (excluded from the
  "no Georgian in components" test).
- Reason: restore is harmless and reversible, so it gets no dialog; both deletes are not.
- Alternatives considered: a separate `/admin/orders/trash` page; an undo toast instead of a
  dialog.
- Why rejected: a separate page duplicates the list's filters and pagination; the owner
  asked for a confirmation dialog.

### 2026-10-18 — Automatic purge runs lazily when the admin opens the order list
- Decision: `order_trash.purge_expired` hard-deletes every order with
  `deleted_at < now() - interval '30 days'` in one `DELETE ... RETURNING`, writes one
  `order.purge` audit row per order (actor NULL, `automatic: true`), and commits — called at
  the start of `GET /admin/orders` (both modes), before the list query. Retention is one
  constant (30 days) in `services/order_trash.py`.
- Reason: Render's free plan has no cron (the refresh-token prune cron was removed for the
  same reason); the admin opens the order list daily, so expired orders go within a day of
  becoming eligible, and nobody else can see them meanwhile.
- Alternatives considered: a cron job or a script; purging on every request; purging on
  application startup.
- Why rejected: no cron on the free plan (a cron can be added later by calling the same
  function); every request adds a write to unrelated traffic; startup purges depend on the
  free instance sleeping and waking.

### 2026-10-18 — Order trash endpoints and their idempotency
- Decision: `POST /admin/orders/{id}/trash`, `POST /admin/orders/{id}/restore` (both 200
  `OrderDetailOut`, idempotent — repeating writes no audit row and keeps `deleted_at`),
  `DELETE /admin/orders/{id}` (204, only for a trashed order, else 409
  `ORDER_NOT_IN_TRASH`), `GET /admin/orders?trash=true`. Every write locks the order row
  `FOR UPDATE`. Audit actions `order.trash`, `order.restore`, `order.purge`. Exact shapes in
  API Contract.
- Reason: a double click or a retry must not fail or write a second audit row; requiring
  the trash before `DELETE` means no single click destroys a live order.
- Alternatives considered: `PATCH /admin/orders/{id}` with `{deleted: true}`; `DELETE` that
  trashes and a second `DELETE` that purges.
- Why rejected: a generic PATCH invites other field edits on an order; the same verb doing
  two different things depending on state is easy to fire twice by accident.
- Note: `scripts/delete_test_product.py` writes `order.delete` for its hard deletes; the
  panel's hard delete is `order.purge`, so the two sources stay distinguishable in the log.

### 2026-10-18 — A trashed order's status is frozen
- Decision: `order_status.transition` refuses a trashed order with 409 `ORDER_IN_TRASH`,
  checked after the row lock (so a trash and a status change racing each other are
  serialised); the detail reports `allowedTransitions: []`. Restore returns the order to the
  status it had.
- Reason: a hidden order that can still move (e.g. be cancelled and restock) changes stock
  from a place the admin does not look at.
- Alternatives considered: allowing transitions in the trash; restoring to `pending`.
- Why rejected: the first breaks "deleting never changes stock" through the back door; the
  second rewrites history the timeline already shows.

### 2026-10-18 — Trash, restore and purge never touch stock
- Decision: no `adjust_stock` call and no write to `inventory_movements` from any trash
  operation; purge leaves the ledger rows with `order_id` NULL (existing FK
  `ON DELETE SET NULL`, `models/inventory.py:73-75`, migration 0003). No restriction by
  status; the confirmation dialog warns that a pending/confirmed/processing order keeps its
  units reserved and that cancelling first returns them.
- Reason: the owner's rule ("deletion does not change stock"); stock moves only through
  checkout, cancellation and admin adjustments, each with a ledger row.
- Alternatives considered: auto-cancel (restock) before trashing; refusing to trash
  non-terminal orders.
- Why rejected: both contradict the owner's request; the dialog makes the consequence
  explicit instead.

### 2026-10-18 — Soft delete with `orders.deleted_at`; trashed orders hidden everywhere but the admin trash and detail
- Decision: migration `0016` adds `orders.deleted_at TIMESTAMPTZ NULL` and a partial index
  `ix_orders_deleted_at (deleted_at) WHERE deleted_at IS NOT NULL` (declared in the model as
  well). Who trashed it is in `admin_audit_log`, no `deleted_by` column. Every reader listed
  in Business Rules → Order trash filters `deleted_at IS NULL` explicitly; the idempotency
  replay lookups (`services/order.py` `place_order`) deliberately do not.
- Reason: restore needs the row intact; one column is the smallest change. No new table,
  so no RLS change. The partial index serves the trash list and the purge, and stays tiny
  because almost no order is trashed. Order numbers come from `order_number_seq`, so a
  purge can never cause a number to be reused.
- Alternatives considered: a separate `deleted_orders` table (copy then delete); a status
  value `deleted`.
- Why rejected: a copy must be kept in step with three tables and needs its own RLS;
  a status would put "deleted" into the state machine and lose the status to restore to.

### 2026-10-18 — Guest carts are priced by a public `POST /cart/quote` (audit A-004)
- Decision: a public, rate-limited (30/min per IP) endpoint returns today's price, stock and
  name for a guest's cart lines; the storefront refreshes a guest's cart with it when the
  cart or checkout opens. It stores nothing and ignores any token. Approved by the owner.
- Reason: a guest's snapshot was taken when the product was added and nothing refreshed
  it, so checkout could show a total (and a free-delivery threshold) the server would not
  charge. Signed-in carts were already fresh through `GET /cart`.
- Alternatives considered: the existing product endpoints, one request per line.
- Why rejected: up to 20 requests per page, and no shared resolution with the saved cart -
  the quote uses the same `services/cart._resolve`, so the two cannot disagree.

### 2026-10-10 — Order and cart share one size cap (20 lines, 10 units)
- Decision: orders and saved carts both take at most 20 products and 10 units each.
- Reason: a saved cart that checkout would refuse is useless; one script could otherwise take a whole catalogue in one request.
- Alternatives considered: cap only the order schema.
- Why rejected: the shopper would reach checkout with a cart it cannot place.

### 2026-10-10 — Extensions stay in `public`; `public` leaves the Data API
- Decision: do not move citext / pg_trgm / unaccent / uuid-ossp. Nothing here uses the
  Supabase Data API (checked: no `rest/v1`, anon key or Supabase JS client), so the owner
  removes `public` from the exposed schemas in the Dashboard.
- Reason: moving an extension without `extensions` on the role's search_path would make
  `users.email` lookups silently case-sensitive and break `word_similarity()`.
- Alternatives considered: `ALTER EXTENSION ... SET SCHEMA extensions`.
- Why rejected: risk on a live database for an advisor warning that the Data API change
  already closes.

### 2026-10-10 — Project state moves to PROJECT.md / PROGRESS.md
- Decision: requirements and new decisions go into this file, tasks and status
  into PROGRESS.md; ASSUMPTIONS.md stays as the record of earlier decisions and
  is referenced, not copied.
- Reason: the agent workflow reads these two files at the start of every session.
- Alternatives considered: moving ASSUMPTIONS.md into this file.
- Why rejected: 550 lines of reasoning already linked from README, code
  comments and tests (`§8.x` references); moving it would break those links.

## Open Questions
- Has anyone other than the owner placed an order? (The storefront is live at
  voltbox-storefront.onrender.com, API on Render free — owner, 2026-10-10.)
- ~~Live Supabase: is the database at migration `0014`?~~ Yes (owner, 2026-10-10); only `0015`
  is left to run there (PROGRESS.md, Deploy plan). RLS is on 15/15 tables per the advisor.
  Update: `0015` ran on live 2026-10-10 (PROGRESS.md, Stage 1 deploy record); Stage 2 adds `0016`.
- Stage 2 (order trash), assumptions taken while planning, 2026-10-18 — correct any that is wrong:
  - ვარაუდი (assumption): nothing is sent to the customer or the owner (no email, no
    Telegram) when an order is trashed, restored or purged.
  - ვარაუდი (assumption): trashing an order that is already in the trash keeps its first
    `deleted_at` (the 30 days do not restart); restore and trash again starts a new 30 days.
  - ვარაუდი (assumption): the trash view lists all trashed orders with the same filters and
    page size as the main list; "days left" is computed in the browser from `purgeAt`.
  - ვარაუდი (assumption): the 30-day purge may run up to a day late (it runs when the admin
    opens the order list); an order past `purgeAt` but not yet purged can still be opened,
    restored or deleted.
  - ვარაუდი (assumption): the audit rows are not shown in the panel (there is no audit
    screen today); they are read in the database when needed.
