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
Stage 3 — Storefront redesign (planned 2026-10-19; tasks T26–T41 in PROGRESS.md). Frontend only:
the shop's look follows `design-reference/Site.dc.html`; nothing the shop does changes.
Stage 2 — Order trash (admin) is done on `agent-system` (T18–T25, finish-check 2026-10-18); its
merge to `main` and its Deploy plan (PROGRESS.md → Stage 2 — Done) are the owner's.
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
- Storefront redesign (owner's request, 2026-10-19) from the mockup
  `design-reference/Site.dc.html` (one 1440px artboard of the **home page**: top bar, header,
  category column + hero, benefits strip, popular categories, one product row, footer; light
  and dark themes in its `renderVals()` → `light` / `darkT`).
  - `DESIGN.md` rewritten from the mockup by the designer: light and dark colour tokens,
    fonts, type scale, spacing, layout widths, radii, shadows, components and states, the new
    logo (SVG) and its favicon variant, and a per-page guide for pages the mockup does not show.
  - Applied to every storefront page: home, category, product, search, cart, checkout, order
    confirmation, login / register / forgot and reset password, account (orders, profile,
    addresses, password), info pages (delivery, returns, privacy, FAQ), 404 — and to the shell
    (top bar, header, category menu, mobile menu, footer, toasts, dialogs, loading/empty/error
    states).
  - The existing light/dark toggle switches between the two new themes.
  - New logo in the header and footer; `public/favicon.svg` from it.
  - Rules: Business Rules → "Storefront redesign"; reasons: Decision Log 2026-10-19.
- Keep the existing behaviour, stack and conventions.

### Out of scope (for now)
- **Any change to the admin panel** (`frontend/src/admin/**`, its look included).
- Any functional change: routes, data shown, forms, validation, cart/checkout/auth behaviour,
  API calls, SEO meta. No new section, feature or text — the mockup's sample copy (hero
  caption "N° 01 — POWER BANK", phone, email, address, hours, product names, prices) is not used.
- Backend, API Contract, database, `render.yaml` / CSP — Stage 3 is frontend only.
- `public/og-image.png` (the shared-link picture) and any PNG icon (apple-touch-icon, web
  manifest) — they keep the old look for now (Open Questions).
- Order-confirmation and password-reset emails (backend templates).
- A new UI or icon library, CSS-in-JS, a design-token build step, Tailwind 4,
  `@playwright/test`.
- Order trash extras: bulk delete / bulk restore, customer- or guest-side order deletion,
  a cron job for the 30-day purge (Decision Log 2026-10-18).
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
    history (CASCADE). What is left is in `admin_audit_log`, which has no FK to the order: the
    `order.purge` row (number, status, total, who, when) and the order's earlier
    `order.status` / `order.trash` / `order.restore` rows — including any free-text `note` an
    admin typed with a status change, which the purge does not remove (Accepted Risks → proposed).
  - A product that appears only in trashed orders still cannot be deleted
    (409 `PRODUCT_IN_USE`, unchanged) until those orders are purged.
- **Storefront redesign** (Stage 3, owner's request 2026-10-19):
  - **Only the look changes.** Every route, what each page shows and does, every handler,
    form, validation message, API call, page title / meta / hreflang / JSON-LD stays as it is.
    Markup may be rearranged only as the layout needs; accessible names, roles, landmarks and
    heading levels stay. Tests that assert behaviour are not edited; an assertion on an old
    class name may be updated to the new class that does the same job.
  - **Copy comes from the current site, never from the mockup.** Text only through the
    existing i18n keys (`frontend/src/i18n/ka.json`, `en.json`); prices from the API; contact
    data from `frontend/src/constants/index.js` (`CONTACT`, `SHOP_FACTS`); the free-delivery
    threshold from `GET /delivery`. A genuinely new UI label (e.g. an `aria-label`) gets a key
    in both files. Decorative ornaments from the mockup (diamond frames, the hero's device
    drawing, numeral eyebrows) are allowed only `aria-hidden` and without words.
  - **The admin panel is frozen.** No file under `frontend/src/admin/` changes. The admin
    palette and the admin value of every non-colour theme token (radius, shadow, icon stroke)
    are pinned by `frontend/src/utils/palette.test.js`. A shared component the admin renders
    (Button, Input, Select, Textarea, Modal, Toast, EmptyState, ErrorState, Skeleton,
    ProductImage, ErrorBoundary) changes only through theme tokens whose admin value is today's
    value, or through a new opt-in prop/variant the admin does not pass.
  - **Both storefront themes meet WCAG 2.x AA**: text 4.5:1, large text (≥ 24px, or ≥ 18.66px
    bold) 3:1, control boundaries and meaningful icons 3:1; `palette.test.js` measures every
    pair `DESIGN.md` lists. Where a mockup value fails, AA wins with the smallest change and
    `DESIGN.md` records both values.
  - **Two themes, one switch.** The existing toggle and rule (the stored pick `theme:v1`,
    else the system setting; `public/theme-init.js` before paint, `src/utils/theme.js` after)
    switch between exactly the two `DESIGN.md` themes. No `dark:` classes (a test fails on them).
  - **Fonts are self-hosted** (`frontend/public/fonts`, `src/fonts.css`): no request to any
    third-party host for fonts, CSS or icons; the CSP (`font-src 'self'`, `style-src 'self'`)
    stays as it is.
  - **Logo and favicon**: the logo is inline SVG in the page (no image request);
    `public/favicon.svg` is the logo's favicon variant from `DESIGN.md`.

## Data
PostgreSQL, Alembic migrations `backend/alembic/versions/0001`–`0017` (`0016` = Stage 2,
`orders.deleted_at`, live since 2026-11-14; `0017` = A-042, `orders.request_hash`; live is at `0016`
until the owner runs `docs/migrations/0017_orders_request_hash.sql`, which has to precede the deploy).
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
**Stage 3 (storefront redesign) adds or changes no endpoint, request, response or error code**
— it is frontend only, and the storefront keeps calling the API exactly as it does now.

This section is the contract between frontend and backend for **the endpoints added or
changed in Stage 2**. Every other endpoint is defined by its route module under
`backend/app/api/v1/routes/` and FastAPI's OpenAPI schema, and is unchanged.

Common to all API endpoints (existing, unchanged):
- Base path `/api/v1`. JSON keys are camelCase (`schemas/base.py`); money is a decimal
  string (`"125.00"`); timestamps are ISO 8601 with timezone (UTC).
- **One error format** (`core/errors.py`), every 4xx/5xx:
  `{"error": {"code": "<STABLE_CODE>", "message": "<English, for logs>", "details": <object | array | null>}}`.
  The UI shows the text for `code` from `frontend/src/i18n/ka.json` → `apiErrors.<CODE>`
  (English: `en.json`, loaded only on `/en`); a code only the admin panel can meet has its text in
  `frontend/src/admin/i18n/ka.json`, Georgian only, loaded with the admin chunk (A-047).
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
- New error codes `ORDER_IN_TRASH` and `ORDER_NOT_IN_TRASH`: `ORDER_IN_TRASH` (a customer can meet it on
  cancel) has Georgian and English text under `apiErrors` in `frontend/src/i18n/ka.json` and `en.json`;
  `ORDER_NOT_IN_TRASH` (admin only) is Georgian only, in `frontend/src/admin/i18n/ka.json` (A-047)
  (`backend/tests/test_error_messages.py` enforces the Georgian text; `i18n.test.js` key parity).

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
  build time (ASSUMPTIONS §6.1). Styling: Tailwind classes named by role; three themes
  (`admin` on `:root` and `[data-admin]`, storefront `theme-light` / `theme-dark` on `<html>`)
  resolved through CSS variables generated in `tailwind.config.js` — the only token source
  (Stage 3 adds radius, shadow and icon-stroke tokens to the same mechanism). Icons:
  lucide-react; fonts self-hosted.
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
  change and profile update; `POST /auth/refresh` alone 30/min — Decision Log 2026-11-12), `POST /orders` 5/min and 30/day, guest order lookup
  10/min, client error reports 20/min, guest cart quote (`POST /cart/quote`) 30/min,
  every other route 300/min per client in one bucket shared across them (`/api/v1/health` and
  `/api/v1/health/live` exempt; a route with its own limit is counted only against that one — Decision Log
  2026-11-16); password reset also 3/hour per email address. Redis-backed in production; client IP
  only through `FORWARDED_ALLOW_IPS` (never `*`).
- A new password (register, change, reset, `manage_admin.py`): at least 8 characters, 12 for an administrator;
  not on the common list (SecLists 10k + the shop's own words, also with digits/punctuation trimmed off the ends);
  not a repetition or simple sequence. Never checked at sign-in, so older passwords keep working (Decision Log
  2026-11-16). An administrator's lock sends one Telegram message (masked email, no IP).
- Production startup refuses unsafe config (CORS `*`, missing
  `TRUSTED_HOSTS`/`FORWARDED_ALLOW_IPS`, short `JWT_SECRET`, ...).
- Every new table must enable RLS in its migration — the Supabase API is
  public, and a table without RLS is readable through it with the anon key.
- Order trash (Stage 2): trash/restore/delete are admin-only through the router-level
  `require_admin` (`tests/test_admin_auth.py` enumerates every admin route). A trashed
  order must not be readable by its customer or a guest token holder, and the guest lookup
  must not tell "trashed" from "missing" (same 404 — order numbers are sequential).
  A purge removes the order's personal data from `orders`, `order_items` and
  `order_status_history`; the `order.purge` audit row keeps only order number, status, total
  and who/when. Not removed: a free-text `note` an admin typed with a status change, kept in that
  change's `order.status` audit row (pre-existing; so a note should not hold customer details).

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
- **A noisy-alpha WebP can go over the image decode budget** (owner, 2026-11-16, AUDIT.md A-103, status: accepted).
  A 1601×1187 RGBA WebP whose alpha channel is noise peaks at 108–113 MiB on Linux during an upload, against
  the 100 MiB `MAX_IMAGE_DECODE_BYTES` budget (measured in the production image; decode is 47–55 MiB, libwebp's
  alpha encoder adds the rest). Accepted because it is not an OOM — two workers at that peak still fit the
  512 MB instance (`config.py`'s arithmetic) — uploading is for administrators only, and a WebP cost strict
  enough to cover it would refuse ordinary transparent product photos (a soft-edged cut-out of that size peaks
  at 82.5 MiB). What still holds: `DECODE_COST["WEBP"] = (71 MiB, 16)`, `MAX_IMAGE_DECODE_BYTES` and the
  per-worker `Semaphore(1)` are unchanged, so one upload at a time per worker and every JPEG/PNG path stays
  inside the budget. Revisit if Render shows memory trouble on the API service (restarts, OOM kills, memory
  near the limit around an image upload).

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

### 2026-11-17 — vitest waits are sized for a loaded machine: testTimeout 15 s, findBy/waitFor 3 s
- Decision: the owner's one-off vitest failure "while pytest ran" was reproduced: three full suites at once
  (`≈`3–6× slower) timed out HomeHero "each opens a category…" in 2 of 6 suites, and Register / catalogNames /
  BrandList once each. Avoidable cost was removed first — HomeHero's per-test `vi.resetModules()` + dynamic
  imports (683 ms of 1.3 s; now `forgetCategories()` beside `forgetDeliveryRules()`), the userEvent keystroke delay
  in the typing-heavy tests (`delay: null`; Register 14 s → 3.7 s), one CartAccountSync test's real 2×800 ms
  debounce (fake timers there), lazy pages preloaded in `beforeAll` where a test waits for them. Quiet: 23 → 6
  tests over 1 s, none over 2 s. What still failed was the cold first test of a file against vitest's 5 s
  `testTimeout` and testing-library's 1 s `findBy*` default, so `testTimeout: 15000` (vite.config.js) and
  `asyncUtilTimeout: 3000` (vitest.setup.js). After: 6 of 6 suites green with the full backend pytest running at
  the same time (≈ 160–211 s per suite).
- Why not tighter tests only: a timeout is a hang detector, not a performance check; the residual was CPU
  oversubscription (vitest beside pytest, the Stop hook's `npm test` beside agents), which no test change removes.
  No test relies on a wait expiring (checked), so a passing test means the same; only a failure takes longer.
- What still holds: CI runs vitest alone; a test that really hangs still fails. CartAccountSync's other real-time
  debounce waits (`waitFor` 2 s against an 800 ms wall-clock debounce) are unchanged — wall time does not stretch
  with CPU load.
- Changes if: a load heavier than the measured one fails again — then the slow test itself, not the limit.

### 2026-11-17 — English is its own chunk; admin-only error texts ship with the admin panel; field errors at their field (A-047, A-089)
- Decision (owner-approved beforehand):
  - **English loads only on `/en`** (A-047). `i18n/index.js` bundles Georgian alone; on an English page
    `languageReady` is a dynamic `import('./en.json')` and `mountWhenReady` mounts the app after it (also after a
    failure, then in Georgian via `fallbackLng`). On a Georgian page `languageReady` is null and the app mounts in
    the same tick — no request, no await. Measured (gzip): the entry's `constants` chunk 22.92 → 12.95 kB
    (http) / 22.89 → 12.92 kB (mock); `en` 9.01 kB, fetched only on `/en`.
  - **A code only the admin panel can meet has its text in `frontend/src/admin/i18n/ka.json`**, Georgian only,
    registered by `admin/adminTexts.js`, which `admin/adminApi.js` imports (every admin request goes through it).
    38 codes moved. Why there: `ka.json` has no admin section — the panel's own words are literal in its
    components, already lazy; what the shop's entry carried was the admin-only `apiErrors`.
    `test_error_messages.py` checks every code in that file is raised only from admin modules (with a named
    exception list), so a customer-facing code cannot be moved there by mistake.
  - **A server refusal that belongs to a field shows at that field, without the generic toast** (A-089) — on
    register, change-password and reset. The new-password reason (common / repetition or sequence / the
    administrator's 12) is told apart by the server's English message, since both rules are one `value_error`
    type; `test_password_policy.py` pins those words. A reason the page does not know gets a general refusal at
    the field.
- What still holds: on `/en` the English chunk is requested only after the entry runs (one more round trip, not
  preloaded). The admin panel is Georgian only; `/en/admin` is not a route. `Profile.jsx`'s taken-email error
  still shows only as a toast in http mode (nit, open).
- Changes if: an admin English UI is wanted (the admin file then needs `en`), or the new-password rules get their
  own codes/types (then the storefront matches `type`, not words).

### 2026-11-16 — A stored APNG is a static PNG; image, password and health-limit nits (A-103–A-106, A-088, A-090–A-095)
- Decision (owner-approved beforehand):
  - **A stored PNG never keeps APNG chunks** (A-104). `_PNG_KEPT` no longer lists acTL, fcTL, fdAT (15 chunks
    now). Every APNG `validate_image` accepts has one frame as Pillow counts it, and the stored file is its IDAT
    picture in every case — a static PNG. Why: a second `acTL` makes Pillow drop the animation and count one
    frame whatever the first said (`PngImagePlugin`, `im_n_frames` reset to None), so such a file passed the
    A-101 one-frame check and the byte strip then kept every fcTL/fdAT, which a browser may animate; an
    `acTL` = 1 file with extra frames kept dead bytes.
  - A-103: the noisy-alpha WebP overrun is accepted, not priced (Accepted Risks).
  - **A decoded image always stores its re-encode** (A-105). The "keep the stripped original when the re-encode
    is not smaller" rule is removed, not narrowed: it ran only for an upright image, and an upright image is
    decoded only when it is over `MAX_STORED_EDGE`, so the rule could only ever store an over-edge file (a
    synthetic 1700×50 `I;16` PNG was kept at 1700 px). AUDIT.md's "only when the original fits the edge" would
    have been a condition that never holds. Consequence: a stored re-encode may be larger in bytes than the
    upload; the edge holds.
  - **The new-password rule catches keyboard walks across two rows** (A-088; the owner asked that the pattern
    rule itself catch `1q2w3e4r!`-type passwords). Two changes in `app/core/security.py`: `is_common_password`
    has a third look-up, the password with only punctuation and spaces trimmed (digits kept, same 4-character
    floor), so `1q2w3e4r!` → `1q2w3e4r` is found on the list; and `is_patterned_password` also removes a
    three-key window that walks two touching rows of a staggered QWERTY layout (`_is_keyboard_walk`: `1q2`,
    `qaz`, `zaq`, `wsx` — each step to a touching key in the next row, same direction sideways; or `q1w` — two
    row neighbours with a touching key between). Ours: kept to touching keys on purpose, because a false
    refusal costs more than a missed walk. Measured on SystemRandom passwords (200 000 per cell): 8 characters
    are refused 1.1–2.3% of the time (0.35–0.74% before), 12 characters under 0.04%, 16 characters ~0.
  - **`/api/v1/health` is limited to 30/min per client; `/api/v1/health/live` stays unlimited** (A-094, owner's
    decision). `/health` runs `SELECT 1` on a pool connection per call, and one address could poll it without
    limit. It now carries its own `@limiter.limit(HEALTH_RATE_LIMIT)` (`"30/minute"`): over it, the same 429
    `RATE_LIMITED` with `Retry-After`; as a decorated route it does not spend the 300/min default bucket
    (tested). `HEALTH_PATHS` is replaced by one exact path, `LIVENESS_PATH` — the only route never counted.
    Why 30: an uptime monitor polls once a minute or less, and a person checking by hand fits beside it.
- What still holds (A-094): Render's Health Check Path and the Dockerfile `HEALTHCHECK` use `/health/live`, which
  is never counted and never answers 429, so a restart can never come from this limit; `backend/render.yaml` and
  the Dockerfile are unchanged. Every other limit is unchanged. Not changed, still open (AUDIT.md A-094's
  "შესამოწმებელი"): slowapi's synchronous Redis hit has no socket timeout set by us; `/health` now makes that hit
  too, while `/health/live` still makes none.
- What still holds (A-088): the rule is checked only when a password is set (register, change-password, reset,
  `manage_admin.py create-admin`), never at sign-in — a stored `1q2w3e4r!` still signs in (tested, customer and
  admin). The refusal is the same 400 `VALIDATION_ERROR`, no new code. Still not caught: word repetition
  (`passwordpassword`), leetspeak (`P@ssw0rd`), walks over three or more rows, walks that skip keys. The common
  list is unchanged (sha256-pinned). The storefront shows a pattern refusal at the password field since A-089
  (2026-11-17 entry).
- What still holds (images): an upright image at or below the edge is never decoded and is stripped byte for byte (a file
  the walk cannot read is still `INVALID_IMAGE` there); a decoded file is no longer walked, so one the walk would
  refuse is stored as its metadata-free re-encode, as A-059 already did. An APNG whose default image is not frame 0 is still refused (Pillow counts two frames), and
  any real animation is `IMAGE_ANIMATED`. `_WEBP_KEPT` still keeps ANIM/ANMF, so a one-frame animated WebP keeps
  them (WebP was not in scope). A PNG made only of kept chunks is still stored byte for byte.
  `MAX_IMAGE_DECODE_BYTES`, `DECODE_COST` and `Semaphore(1)` are unchanged.
- How it changes: keeping an APNG chunk again needs Pillow's frame count to be checked against every `acTL`
  first.

### 2026-11-16 — Animated images are refused; a damaged image is a 400, never a 500; WebP cost re-measured (A-096–A-102)
- Decision (owner-approved beforehand; values that were left to us are marked):
  - **Animation is not needed for a product photo** (A-101). `validate_image` refuses any image Pillow counts
    more than one frame in (`n_frames`, read at open, no frame decoded) — APNG and animated WebP, at any size —
    with 400 `IMAGE_ANIMATED` (words in `admin/i18n/ka.json` since A-047; the admin upload shows it like the other image
    errors through the generic `apiErrors.<code>` lookup). It sits after `verify()` and the format check (a broken
    file is still `INVALID_IMAGE`, HEIC still `UNSUPPORTED_IMAGE_FORMAT`) and before the pixel limit. Why refuse
    rather than keep animation: the two storage paths disagreed — a file that fits kept every frame, a reduced one
    became its first frame.
  - A file Pillow cannot read is `INVALID_IMAGE` whichever step finds it (A-096, A-097): `SyntaxError` joins
    `validate_image`'s except (a PNG cut inside its last chunk header), and `shrink_to_fit` turns a closed list of
    Pillow's bad-bytes errors (`OSError`, `ValueError`, `SyntaxError`, `IndexError`) into `INVALID_IMAGE` around
    only the two calls that decode (`thumbnail`, `transpose`). Ours: the list is closed and the encoder is outside
    the wrap, so a bug in our code is still a 500. `IndexError` also joins `validate_image`'s except (A-102, found
    by the re-review): a JPEG whose SOF lists fewer components than it declares, a PNG with no IDAT.
  - A stored JPEG keeps only JFIF's 14-byte header with the thumbnail size 0×0 and Adobe's 12 bytes (A-098); a
    shorter JFIF/Adobe payload is kept as it is (ours: it has no thumbnail, and Pillow reads it today).
  - `import_products.py` refuses `reviewsCount` outside 0..2 147 483 647 (the int4 column; nothing else caps it)
    and a flag (`isActive`/`isFeatured`/`isNew`) that is not a JSON bool, `null` included, before any write (A-099).
  - WEBP's `DECODE_COST` stays `(71 MiB, 16)` after a Linux re-measurement with `method=5` (A-100): a soft-edged
    cut-out reaches the 100 MiB budget between 2.3 and 2.6 MP, so no lower cost is justified.
- What still holds: a one-frame APNG (`acTL` = 1) or one-frame animated WebP is accepted; the WebP keeps its
  animation chunks (ANIM/ANMF), an APNG has been stored as a static PNG since A-104 (entry above). An APNG whose
  default image is not its first frame counts as two frames in Pillow and is refused (conservative); one with two
  `acTL` chunks counts as one (AUDIT.md A-104). `MAX_IMAGE_DECODE_BYTES`, `DECODE_COST` and `Semaphore(1)` are unchanged. The bad-bytes
  list was measured on the Pillow in `.venv`; another Pillow version may raise another type for some other malformed
  chunk. **Not held:** a 1601×1187 RGBA WebP with noise in its alpha channel peaks 108–113 MiB on Linux, over the
  budget (AUDIT.md A-103; accepted by the owner, see Accepted Risks); the WEBP fixture of `TestDecodeMemoryIsBounded`
  is flat and cannot show it.
- How it changes: allowing animation again means deciding what a reduced one becomes (all frames re-encoded, with
  its own decode cost) before removing the check. Pricing WebP for noisy alpha (an unmeasured estimate of 1.0–1.5 MP;
  to be measured first) was not chosen: the owner accepted the overrun (A-103, Accepted Risks).

### 2026-11-16 — Image strippers are allowlists; WebP method 5; order-number zone from settings (A-055–A-059, A-075, A-077–A-079)
- Decision (all approved by the owner beforehand; values that were left to us are marked):
  - Stored images keep only chunks known to be harmless (A-058): PNG — 18 decode/colour/pHYs/APNG chunks (15 since
    A-104: the APNG ones were dropped); WebP —
    VP8X, VP8, VP8L, ALPH, ANIM, ANMF, ICCP, and inside an ANMF frame only ALPH/VP8/VP8L; JPEG — APP0 only with
    `JFIF\0`, APP14 only with `Adobe`, APP2 only with `ICC_PROFILE\0`.
  - The WebP walk refuses a file past `_MAX_WEBP_CHUNKS = 65_536`, one budget for the file and all its frames
    (A-075, confirmed: 5 MiB of empty chunks cost 285 ms, now 33 ms). Value ours, same as `_MAX_JPEG_MARKERS`.
  - WebP re-encodes with `method=5` (A-056, ours after measuring): `method=6` took 2.2–4.0 s on any WebP with
    partial transparency vs 0.2–0.7 s, for a file 2–4% smaller, while holding the single decode slot.
  - A PNG's EXIF is read from its chunk list wherever `eXIf` sits (A-057), so a late one rotates like an early one
    and is costed the same way.
  - A resized file whose byte-level walk fails is stored as its re-encode instead of refused (A-059).
  - The order number's date uses `settings.store_timezone` as a bind parameter (A-077), and `Settings` refuses an
    unknown `STORE_TIMEZONE` at startup (ours: the change had made a typo break every checkout).
  - `import_products.py` refuses stock outside 0..`MAX_STOCK`, `lowStockThreshold` outside
    0..`MAX_LOW_STOCK_THRESHOLD` and non-integers before any write (A-078). `MAX_STOCK`, not the admin form's
    100 000, because `adjust_stock` enforces only `MAX_STOCK` and an import is a bulk restock (ours).
- What still holds: `MAX_IMAGE_DECODE_BYTES`, `DECODE_COST` and `Semaphore(1)` are unchanged; the WEBP
  `DECODE_COST` pair was measured with `method=6` on Linux (re-measured with `method=5` on 2026-11-16, A-100 —
  kept; see the entry above). The ICC profile is still kept whole; an allowlisted APP0 JFIF / APP14 Adobe segment is
  cut to its header since A-098. Timings are Windows-only. zoneinfo, not Postgres, validates the zone name.
- How it changes: add a chunk to an allowlist only with a reason it cannot identify anyone.

### 2026-11-16 — New-password rule, administrator minimum 12, Telegram on an administrator's lock (A-037, no TOTP)
- Decision (owner-approved scope; details chosen in the fix): `_validate_password` (register, change-password,
  reset) refuses, besides < 8 characters, (1) a password on the common list, compared lower-cased, whole or with
  digits, punctuation and spaces trimmed off both ends when that core is ≥ 4 characters (`Password1!` → `password`);
  (2) a pattern: every character inside a 3-character window of one repeated character, a ±1 step among digits or
  letters, or three adjacent keys of a keyboard row is removed, and fewer than 5 distinct characters may not remain
  (`MIN_DISTINCT_CHARACTERS`). Since A-088 also a walk across two keyboard rows, and a third list look-up that
  keeps edge digits (entry at the top of the log). An administrator's new password needs 12 (`MIN_ADMIN_PASSWORD_LENGTH`), checked in the
  service where the role is known (change-password before anything is counted; reset under the row lock before the
  link is spent, so a refusal leaves it usable) → 400 `ADMIN_PASSWORD_TOO_SHORT`; `manage_admin.py create-admin`
  applies all of it; `promote-user` sets no password and says so. Login never checks the rule.
- The list: SecLists `Passwords/Common-Credentials/10k-most-common.txt`, upstream commit `913b327`, 10 001 entries,
  **MIT License (Copyright (c) 2018 Daniel Miessler)**, kept byte-identical at `backend/app/core/common_passwords.txt`
  with `common_passwords.NOTICE.txt` (source, commit, sha256, license text); the shop's 17 old words are merged in
  code. A test pins the sha256 and the count, so changing the data is a visible decision. Shipped in the image
  (checked in a built image: wheel and `COPY app` both carry it).
- Lock notice: `_record_failure`'s conditional UPDATE returns the new `locked_until`; only the guess that set the
  lock on an admin row builds a message (`b***@example.ge`, until HH:MM Asia/Tbilisi, no IP or user agent). It is
  carried on `AppError.after_response` and sent as a Starlette background task after the committed refusal — a
  FastAPI `BackgroundTasks` is dropped when the route raises. A Telegram failure is one ERROR line and never changes
  the response. A customer's lock sends nothing.
- What still holds: lockout itself is unchanged (10 failures → 15 minutes), so whoever knows an admin email can still
  keep the panel locked — now the owner sees it, but it is not prevented until TOTP (separate stage). The frontend
  still only knows the 8-character minimum and shows the generic validation text for a pattern refusal.

### 2026-11-16 — The default rate limit is 300/min per client, enforced by an app-wide dependency (A-080)
- Decision (owner-approved: 300/min, health exempt, same 429): every route without its own `@limiter.limit` is
  counted against `DEFAULT_LIMIT = "300/minute"` in one bucket per client address shared by all of them (slowapi's
  *application* limit), by `enforce_default_limit`, a FastAPI dependency on the whole app. `/api/v1/health` and
  `/api/v1/health/live` are exempt by exact path (since A-094 only `/health/live`; `/health` has its own 30/min); `/sitemap.xml` is counted; a CORS preflight, a path with no
  route (404/405) and a body FastAPI cannot parse (malformed JSON or multipart → 400, oversized → 413; the
  dependency runs after the body is read) are not — none of them reaches the database. A schema-validation 400
  is counted. A decorated route is counted only against its own limit. The 429 is the same
  `RATE_LIMITED` envelope with `Retry-After`; the WARNING keeps the A-036 pseudonym.
- Reason: `SlowAPIMiddleware` found no handler under FastAPI 0.141 (`_IncludedRouter` in `app.routes`) and checked
  nothing — the documented 60/min never applied (measured: 70 × 200). A dependency runs after routing, where the
  matched route is always known. One shared bucket, because slowapi's per-route default is scoped by URL and
  `/products/<slug>` would give a catalogue walker a fresh bucket per product.
- The ceiling is high on purpose until `FORWARDED_ALLOW_IPS` is confirmed on Render (A-036, PROGRESS.md Blockers):
  if the API sees the proxy instead of the client, the whole shop shares one bucket, and 300/min keeps that from
  becoming an outage. Once confirmed, it can be lowered (one constant in `app/core/rate_limit.py`).
- What still holds: auth 5/min, refresh 30/min, orders 5/min + 30/day, lookup 10/min, client errors 20/min,
  quote 30/min, reset 3/hour per address — unchanged. Uses slowapi's private `_check_request_limit` and
  `_should_exempt` (the calls its own middleware made; slowapi is pinned in the lock).

### 2026-11-15 — Logs name a client only by a keyed pseudonym; transport and header hardening (A-036, A-046, A-011, A-010, A-063)
- Decision (owner-approved scope; the details chosen in the fix): the access line's `client` and slowapi's
  "ratelimit exceeded" WARNING carry the first 12 hex chars of HMAC(HMAC(JWT_SECRET, a fixed label), client
  address); gunicorn's own access log is off (`accesslog = None`), because under UvicornWorker it printed the
  raw IP. `Server` is dropped by a UvicornWorker subclass (`app/core/uvicorn_worker.py`, under `app/` so the
  Dockerfile ships it). A 429's `Retry-After` is the seconds left in the failed limit's window, falling back
  to the window length. `DB_SSL_MODE=require` with `DB_SSL_ROOT_CERT` set keeps verifying fully, and a
  deployed `require` without it logs a warning instead of refusing. The storefront's HSTS is `max-age=300`
  until voltbox.ge. The compose `api` service has no `env_file`, and its external credentials are blank.
- Reason: the rate limiter's IP source had to become checkable from the log without the log holding IPs.
  A plain hash of an IPv4 is reversible by enumeration. A configured CA should never be dropped silently.
  Production must keep starting on today's settings until the owner installs the Supabase CA.
- What still holds: the admin audit log still stores the IP in the database. Rotating JWT_SECRET changes
  every pseudonym. Production's effective DB mode is still `require` (encrypted, not authenticated) until
  the owner switches (PROGRESS.md Blockers). How to change: the HSTS value and the DB mode are a Render/
  render.yaml edit each (docs/deployment.md §7, "ბაზასთან TLS").

### 2026-11-15 — A repeated Idempotency-Key is compared on the request too (A-042)
- Decision: `orders.request_hash` (migration 0017, nullable `VARCHAR(64)`, no index) holds the SHA-256 of the
  canonical request: merged quantities ordered by product id, the validated customer with email and phone
  normalised the way `owns_order` compares them, and the payment method. A repeat of the key by its owner with
  a different hash is 409 `IDEMPOTENCY_KEY_REUSED`; on both replay paths (the pre-check and the unique-index
  clash). Owner-approved.
- Reason: the key alone answered "qty 5" with the stored "qty 1" order under a 201. Email/phone are normalised
  so a retry that differs only in case (`Giorgi@Example.GE`) still replays, as it did before.
- What still holds: the owner check runs first, so a stranger still gets `IDEMPOTENCY_KEY_CONFLICT` and learns
  nothing; any other change to name, address, city or comment counts as a different request; orders placed
  before 0017 carry NULL and are compared on the key alone. The storefront issues a new key whenever its
  checkout signature (items, contact, payment) changes, so a normal checkout never meets the new 409.

### 2026-11-15 — The JPEG walker refuses a file past 65 536 markers (A-060)
- Decision: `_strip_jpeg` counts every marker it consumes and answers `INVALID_IMAGE` past
  `_MAX_JPEG_MARKERS = 65_536`; fill bytes are skipped with one regex match instead of a byte loop.
- Reason (the owner left the number to us): measured, a legitimate file has a few dozen markers — 12 baseline,
  27 for a 4000×3000 progressive JPEG with EXIF and ICC, 13 with a restart marker per block — because stuffed
  bytes and restart markers inside a scan are copied in bulk and never turn the loop. 65 536 markers cost 27 ms;
  the 5 MiB hostile files that took 1.1 s (`FF 01`) and 1.5 s (`FF FF 00` in a scan) now stop in 35 / 84 ms.
  A lower cap (4 096) would save nothing worth having and leaves less room for unusual phone files.
- What still holds: only Pillow-made files were measured, not phone files with MPO or extended XMP. (The WEBP
  stripper's missing cap, A-075, was confirmed and closed 2026-11-16: `_MAX_WEBP_CHUNKS`.)
- How it changes: lower the constant if a measurement on the production image shows the cap costing more than
  ~100 ms.

### 2026-11-15 — Every address write queues on the owner's row; at most 20 addresses (A-041, A-071)
- Decision: `address.create`, `update_one` and `remove` all take `_lock_default_writes` (FOR NO KEY UPDATE on the
  owner's `users` row) first; `create` counts under it and refuses the 21st with 409 `ADDRESS_LIMIT_REACHED`.
  `User.addresses` is `lazy="raise"` (+ `passive_deletes=True`), so `GET /auth/me` is one statement.
- Reason: "count, then insert" lets two creates at 19 leave 21, and a delete outside the queue let an update
  that had read the address hit `StaleDataError` (a 500, reproduced) and a create count a row being deleted
  (a spurious 409). One queue for all of a user's address writes closes all three; only that user's own
  address writes wait on each other. This supersedes "a plain address is created without waiting" in the
  A-040 entry below.
- What still holds: the A-040 lock level and `populate_existing` are unchanged; lock order is always users →
  addresses. The races are tested at the service level, not over HTTP.

### 2026-11-15 — Input bounds: page ≤ 10 000, a stock change within ±100 000, a search reads 16 tokens (A-038, A-007, A-045, A-072, A-073, A-074)
- Decision: one `MAX_PAGE = 10_000` on every `page` input; `StockAdjustRequest.change` within
  ±`MAX_STOCK_ADJUSTMENT` (100 000); a search query is read up to `MAX_QUERY_TOKENS = 16` (stopwords not
  counted, the rest dropped silently). All owner-approved values; out-of-range is 400 `VALIDATION_ERROR`.
- Update 2026-11-15 (A-074): the search cap went from 8 to 16 tokens (owner-approved). It still counts
  normalized tokens — `normalize` splits "100W", "2მ", "USB-C" in two and repeats count — so a full product name
  of ~8 typed words is ~12 tokens; 8 cut such a name short. No dedupe, no change to counting.
- Update 2026-11-15 (A-072, A-073): a product's stock total is held to `inventory.MAX_STOCK = 1_000_000` in
  `adjust_stock` (400 `STOCK_LIMIT_EXCEEDED`, every increase, a cancellation's restock included; a decrease is
  never refused); initial stock ≤ `MAX_STOCK_ADJUSTMENT`, `low_stock_threshold` ≤ 100 000, category `position`
  ≤ 10 000 (400 `VALIDATION_ERROR`). All owner-approved. No database CHECK and no migration for the stock total
  (orchestrator's call: the owner approved only 0017's `request_hash`, and `adjust_stock` is the only writer).
  What still holds: `scripts/import_products.py` pre-checks the stock and threshold bounds since A-078
  (2026-11-16) but not `reviewsCount` (AUDIT.md A-099); the admin forms resend `position`/`lowStockThreshold` on every save, so a live row already above a
  bound is not saveable from the panel until that value is lowered (PROGRESS.md Blockers has the check).
- Zero stock change: the owner approved "zero forbidden". It already was — `adjust_stock` answers 400
  `EMPTY_ADJUSTMENT`, which has ka/en text and a test — so it keeps that code instead of becoming
  `VALIDATION_ERROR` (no API or i18n change).
- What still holds: the search cap counts normalized tokens, so "100W" or "USB-C" count twice (A-074 raised the
  cap rather than changing the count). (The stock-total and admin-int gaps once listed here are closed by
  A-072/A-073 above.)

### 2026-11-15 — A Postgres DETAIL value is cut to the end of its line (A-067)
- Decision: `PG_DETAIL_VALUE` matches `Key (…)=(` and `Failing row contains (` and drops everything after them
  on that line.
- Reason: NOT NULL / CHECK violations quote the whole row (guest email, phone, password hash); stopping at the
  next `)` leaks the rest of a value that contains one. The words after the value (`already exists.`) go too;
  the constraint name on the line above still says what was violated. This closes the A-067 note in the A-034
  entry below.
- What still holds: later lines of a multi-line value (`notes`) are not scrubbed.

### 2026-11-14 — The server's own loggers write through our JSON handler (A-034)
- Decision: `configure_logging()` (run from the lifespan) clears the handlers of `uvicorn`, `uvicorn.error`
  and `gunicorn.error` and lets them propagate to the root JSON handler; `JsonFormatter` scrubs the message
  and a pre-rendered `exc_text` as well as `exc_info`.
- Reason: under gunicorn, `UvicornWorker` gives `uvicorn.error` gunicorn's own plain handlers with
  `propagate=False`, so the "Exception in ASGI application" traceback after a 500 skipped `scrub` and
  carried Postgres's `Key (email)=(…)` into the log. A scrubbing filter on gunicorn's handlers was the
  alternative; rejected because it keeps a second, plain-text format and a second place the rule lives.
- Visible consequence: those lines are now JSON on stdout with `"logger": "uvicorn.error"`, not gunicorn's
  `[pid] [LEVEL]` text on stderr — a log filter written for the old text needs updating.
- What still holds: the gunicorn master never runs `configure_logging()` and stays plain text (it logs
  workers starting and exiting, no request data), and so do a worker's errors before the lifespan.
  `scrub` still knows only the `Key (…)=(…)` shape — `Failing row contains (…)` is open as AUDIT.md A-067.

### 2026-11-14 — Default-address writes queue on the owner's row (A-040)
- Decision: `address.create` (only for a default) and `address.update_one` (always, before the read) take
  `FOR NO KEY UPDATE` on the owner's `users` row; `_get_owned` and `list_for_user` read with
  `populate_existing`.
- Reason: "clear the old default, then write the new one" raced to `uq_addresses_one_default_per_user`
  (a 500). `FOR NO KEY UPDATE` rather than the audit's `FOR UPDATE`: it serializes the same way and is the
  level `auth.py` already takes on that row, but does not block the `FOR KEY SHARE` of FK checks (orders,
  tokens, addresses inserts). `populate_existing` because `get_current_user` loads the addresses
  (`selectin`) on the same session before the lock; a waiting request otherwise wrote against a stale
  `is_default` and left the user with no default.
- What still holds: a plain address is created without waiting; unsetting the only default still leaves
  none (as before); a concurrent DELETE and PUT of one address may still 500 (AUDIT.md A-071, pre-existing).

### 2026-11-12 — Every stored image loses its metadata; a rotated one is re-encoded upright (A-033)
- Decision (approved by the owner beforehand): replaces the old `shrink_to_fit` rule "an image that fits is
  stored untouched". Now every upload is stripped of EXIF/GPS, XMP, IPTC, comments and trailing data:
  byte-level and lossless (`_strip_jpeg` / `_strip_png` / `_strip_webp` in `app/services/storage.py`) when the
  image fits and is upright; re-encoded only when it is larger than `MAX_STORED_EDGE` or its EXIF Orientation
  is not 1 (reduce first, then rotate). The ICC profile is kept — on a re-encode only when its colour space
  matches what is saved (a CMYK profile on the RGB it becomes would colour it wrongly).
- Reason: the bucket is public. A 1200×900 phone photo used to be published byte for byte with its GPS
  coordinates and device; a 4000×3000 one with Orientation 6 was stored sideways (the resize dropped the tag).
  "A re-encode loses quality" still holds, which is why the clean case is byte-level and pixel-identical.
- Also changed: the decode budget now applies to every image that is decoded, so a small image with
  Orientation ≠ 1 is costed too (`DECODE_COST` and its formula unchanged). The only uncosted path is now
  ≤ 1600×1600 AND Orientation 1, which is never decoded. Consequence: a WebP above 1.9 MP that needs turning
  is refused with `IMAGE_TOO_MANY_PIXELS`. Measured (Windows) worst cases of that path: WebP 90.4–90.6 MiB,
  JPEG 30.7, PNG 20.8 against the 100 MiB budget (`TestDecodeMemoryIsBoundedWhenOnlyTurning`); the source
  bitmap is released before encoding, without which the WebP case measured 97.7 MiB.
- What still holds: a file with nothing to strip is stored byte for byte; the format is preserved; a file
  that fits, is upright and whose container cannot be walked is refused with `INVALID_IMAGE` (never decoded
  instead — that path is unbudgeted), so a truncated small JPEG without EOI, once stored, is now refused. Since
  A-059 (2026-11-16) a resized or turned file whose walk fails is stored as its clean re-encode instead.
  Orientation is read from EXIF only, header-only; since A-057 a PNG's `eXIf` counts wherever it sits.

### 2026-11-12 — Upload decoding runs in a thread, one at a time per worker (A-032)
- Decision: `admin_image.prepare_upload` runs `validate_image` + `shrink_to_fit` in one `asyncio.to_thread`
  hop behind a module-level `asyncio.Semaphore(1)` (`_PROCESSING`), the same pattern as `_HASHING` in
  `app/core/security.py`. The PNG re-encode no longer passes `optimize=True`.
- Reason: on the event loop a PNG upload stalled every other request for 6.5–8.2 s (audit measurement) and
  killed a gunicorn worker at `timeout=5`. `optimize=True` was most of that: locally 5.2 s → 1.7 s for a
  photo-like 2800×2100 RGBA PNG, for a file about 10% larger.
- What still holds: one decode per worker process, so the memory ceiling stays `MAX_IMAGE_DECODE_BYTES` per
  process and `WEB_CONCURRENCY` times that per deployment (except a WebP with noise in its alpha channel, measured
  up to 113 MiB against the 100 MiB budget — AUDIT.md A-103); `DECODE_COST` and `TestDecodeMemoryIsBounded`
  unchanged. JPEG keeps `optimize=True` (0.2 s). WebP moved from `method=6` to `method=5` on 2026-11-16 (A-056,
  measured; see the entry of that date).
- How to change: raising the semaphore multiplies the memory ceiling by its value.

### 2026-11-12 — `/auth/refresh` has its own limit, 30/min (A-031)
- Decision: `REFRESH_RATE_LIMIT = "30/minute"` (`app/core/rate_limit.py`) on `POST /auth/refresh` instead
  of `AUTH_RATE_LIMIT` (5/min). Value approved by the owner.
- Reason: 5/min stops password guessing, and refresh has no password — it is spent with an
  `HttpOnly; SameSite=strict; Path=/api/v1/auth` cookie holding a 384-bit (`secrets.token_urlsafe(48)`) rotated token. At 5/min shoppers
  behind one NAT/CGNAT address whose access tokens expire together got 429 (measured: the 6th refresh), which
  the storefront treated as a logout (A-030). 30/min carries them and still caps a script.
- What still holds: login, register, forgot/reset password, change-password and profile update stay at
  5/min per address; reset emails also 3/hour per address.
- How to change: the constant; `test_refresh_allows_far_more_than_login_before_it_is_limited` derives its
  count from it.

### 2026-11-12 — A failed refresh ends the session only on 401 (A-030)
- Decision: `refreshSession` (`frontend/src/services/session.js`) clears the session only when
  `/auth/refresh` answers 401 (or 2xx without a token). 429, 5xx, any other status and a network error keep
  it and return null; `httpClient.request()` then throws a temporary `ApiError` (`apiErrors.fallback`,
  status 0) instead of `SessionExpiredError`, because the stored session is still there.
- Reason: the refresh route raises only `UnauthorizedError` (401: `INVALID_REFRESH_TOKEN`,
  `ACCOUNT_DISABLED`), so only a 401 says the token is dead; a rate limit, a deploy or a database blip says
  nothing about it. 403 is not treated as "ended" — the route never returns it.
- What still holds: a dead refresh token still clears the session, notifies listeners and redirects a
  foreground request to login; a background cart sync still never redirects; a guest's 401 still falls
  through. A 429 refresh shows the generic message, not `RATE_LIMITED` — that would need `refreshSession`
  to return the status; judged not worth it.

### 2026-10-19 — Theme foundation details (T27)
- Decision: the mockup fonts are three variable woff2 files (Cormorant Garamond latin 400–600, Noto Serif
  Georgian georgian and latin 300–500) — Google serves nothing else for these weights. `₾` (U+20BE) is in
  none of the loaded subsets (only latin-ext), so a system serif draws it, as before. Cormorant's default
  digits are old-style, so every price set in `font-display` also sets `lining-nums`. "No shadow" in a theme
  is `0 0 #0000`, not `none` (Tailwind puts ring and shadow in one `box-shadow` list, and `none` would void
  the focus ring). The focus-ring corner is a token (`--focus-radius`: admin 0.125rem, shop 0). Storefront
  base type, link hover, `::selection` and the theme fade sit on `[data-storefront]`, never on `body`.
- Reason: the admin shares `body`, the global focus rule and every token; scoping keeps its look identical,
  and `palette.test.js` pins each admin value. What still holds: no third-party request, CSP unchanged.
- How to change: a fourth font file (latin-ext) would draw `₾` in the mockup fonts — one `@font-face` each.

### 2026-10-19 — The mockup's `line2` keeps its value on labelled controls; text fields get an AA border (T26)
- Decision: a new colour role `outline` carries the mockup's `line2` unchanged (light #D6CDBC, dark #3A3A40,
  admin = today's outline-button border) for borders of controls that carry their own label or icon: outline
  and secondary buttons, round icon buttons, the categories button, the hero's outline link. `ink-300`
  (control borders) moves to #8C8474 / #6A6A70 (≥ 3:1) and stays the boundary of text fields, select,
  checkbox/radio and the quantity stepper. The mockup's light `gold`, `goldTxt` and `muted` move by the
  smallest step that passes AA where they are text or a meaningful mark on the footer and the page.
- Reason: WCAG 1.4.11 asks 3:1 only of a boundary that alone identifies the control; a labelled button is
  identified by its label. Darkening `line2` everywhere (the first DESIGN.md draft) made every outline button
  harsher than the mockup the owner wants reproduced. What still holds: every text and every text-field
  boundary meets AA in both themes, and `palette.test.js` measures them.
- How to change: if the owner wants 3:1 on every border, set `outline` = `ink-300` in the light and dark
  palettes (one value each); no component changes.

### 2026-10-19 — Stage 3 work stays on branch `agent-system`
- Decision: every Stage 3 commit goes on `agent-system`, one commit per task; no new branch.
  Push and merge to `main` only with the owner's approval (unchanged).
- Reason: the owner asked for it. This overrides the kit's per-task `team/<name>` branch rule
  for this project.
- Consequence recorded: Stage 2 (order trash) is on the same branch and not yet merged; if the
  owner wants Stage 2 live before the redesign, `main` takes the commit Stage 3 starts from
  (`db9a242`) first. Recorded in PROGRESS.md → Stage 3 deploy notes.
- Alternatives considered: a `redesign` branch off `agent-system`.
- Why rejected: the owner's explicit instruction.

### 2026-10-19 — The two new themes re-point the existing `light` / `dark` palettes; `admin` is frozen and pinned
- Decision: `tailwind.config.js` keeps its three palettes. `light` and `dark` get the mockup's
  values (via `DESIGN.md`), each role keeping its job (`ink-50` page, `surface` cards, `ink-300`
  control borders, `primary-600` solid fill, `primary-700` text/link, …). Roles the mockup
  needs and the palette lacks (e.g. text on a solid fill — the mockup's dark buttons have dark
  text, so `text-white` no longer fits; gold for ornaments and icons; footer background) are
  added to **all three** palettes, with the admin value equal to what the admin renders today
  (the "same tokens in every theme" test enforces the shape). Radius, shadow and the icon
  stroke width join the same CSS-variable mechanism (`:root` / `[data-admin]` /
  `:root:has([data-admin])` = admin = today's values; `.theme-light` / `.theme-dark` = new). A new
  test in `palette.test.js` pins every admin value to today's literal, so an edit that would
  move the panel fails.
- Reason: the admin imports the shared Button, Input, Select, Textarea, Modal, Toast,
  EmptyState, ErrorState, Skeleton and ProductImage, and Modal and Toast render through a portal
  into `<body>` — outside `[data-storefront]`, so a `storefront:` class cannot reach them, but a
  CSS variable on `<html>` can. Changing `rounded-control` or `shadow-popover` globally would
  reshape the panel.
- Alternatives considered: new storefront-only components; separate token names for the shop;
  a copy of the shared components for the admin.
- Why rejected: duplicates ten components or every class name, and the portals still escape
  `[data-storefront]`; the variable mechanism already does exactly this for colour.
- What still holds: the panel's look, its tests, `data-admin`, `public/theme-init.js` skipping
  `/admin`.

### 2026-10-19 — Mockup fonts are self-hosted, only the weights `DESIGN.md` uses
- Decision: Cormorant Garamond (Latin display — wordmark, prices, Latin headings) and Noto Serif
  Georgian (Georgian headings) are added as woff2 files in `frontend/public/fonts` with
  `@font-face` + `unicode-range` in `src/fonts.css`, like the existing Noto Sans Georgian (whose
  eight files stay — the admin uses them). Only the weights and subsets the `DESIGN.md` type
  scale uses (planning ceiling: Cormorant Garamond latin 400/500/600, Noto Serif Georgian
  georgian+latin 300/400/500, Noto Sans Georgian +300 only if the scale uses it). Files come
  from the Google Fonts css2 API once, by hand (SIL OFL 1.1); `fonts.css` records where from and
  when — its comment's reference to `scripts/fetch-fonts` is wrong (no such script) and is
  corrected. At most two preloads in `index.html`.
- Reason: `src/fonts.css` already rejects the Google CDN (privacy: every visitor's IP to
  Google; two extra handshakes before first paint; no cross-site cache any more). The CSP's
  `font-src 'self'` covers self-hosted files, so `render.yaml` does not change.
- Alternatives considered: the mockup's Google Fonts `<link>`; `@fontsource/*` npm packages.
- Why rejected: the first breaks the CSP and the privacy decision; the second adds dependencies
  and lockfile churn for files that are copied once.

### 2026-10-19 — `DESIGN.md` is rewritten; its admin parts move verbatim into a frozen section
- Decision: the designer rewrites `DESIGN.md` from the mockup (owner's request). Everything the
  admin still relies on — the admin column of the colour table and its contrast numbers, admin
  typography, admin components (DataTable, sidebar, banners, StatusBadge, ConfirmDialog) and
  §9 "Admin: destructive actions and trash" — moves unchanged into a final "Admin panel
  (frozen)" section; only section numbers change.
- Reason: Stage 2's design and the admin code refer to those rules; the panel is not part of
  the redesign, so its spec must not be lost or silently restyled.
- Alternatives considered: a separate `DESIGN-ADMIN.md`.
- Why rejected: one more file to keep in step; one document with a clearly frozen part is enough.

### 2026-10-19 — Pages the mockup does not show are styled from `DESIGN.md`'s components, not redesigned
- Decision: the mockup covers the home page and the shell only. Every other page keeps its
  current structure and content and gets the mockup's language through the shared components
  and a per-page guide in `DESIGN.md` (hairline `line` borders, near-square radius, serif
  headings, gold eyebrow/ornament, dark solid buttons, generous white space). No page gains or
  loses a section.
- Reason: "only the look changes"; a new layout per page would be a product decision the owner
  has not made.
- Alternatives considered: designing each page anew in the mockup's spirit.
- Why rejected: risks functional drift and needs owner review of designs that do not exist.

### 2026-10-19 — Icons stay lucide-react, thinner through one token; the logo is the only new drawing
- Decision: keep lucide-react (already a dependency, also used by the admin). The mockup's
  thin line (stroke ≈ 1.1–1.5) comes from one rule in `index.css`,
  `.lucide { stroke-width: var(--icon-stroke) }`, with the admin value 2 (lucide's default, so the
  panel is unchanged). Category icons stay `CategoryIcon` (lucide); the mockup's diamond frame
  around them is CSS/SVG decoration. The logo mark (and its favicon variant) is the only
  hand-drawn SVG, kept in one component (`Logo.jsx`, exporting the mark for footer and hero).
- Reason: the simplest way to get the mockup's look without a second icon set; no component
  passes `strokeWidth` today (checked), so the rule is the only source of the width.
- Alternatives considered: copying the mockup's hand-drawn icons; another icon library.
- Why rejected: hand-drawn icons have to be maintained for every new category; a library is a
  new dependency for the same result.

### 2026-10-19 — Product photos stay on a light tile in both themes
- Decision: the `media` role (photo tile) stays light in both storefront themes, as today,
  restyled to the mockup's light `imgBg` tone; the mockup's dark tile is used only where there
  is no photo (placeholder), if `DESIGN.md` wants it.
- Reason: real product photos have white backgrounds and `storefront:mix-blend-multiply`
  blends them into the tile; on a dark tile multiply darkens the product itself. The mockup
  shows only a placeholder icon, so it does not answer this.
- Alternatives considered: the mockup's dark tile for photos in the dark theme.
- Why rejected: products would render darker than they are; cutting out every photo is not
  available (the owner uploads them as they are).

### 2026-10-19 — Browser checks: one screenshot script on the existing `playwright` library
- Decision: keep the 2026-10-18 decision (no `@playwright/test`). T28 adds
  `frontend/scripts/e2e/screens.mjs`: against a mock-mode preview build it screenshots every
  storefront route in both themes at 1440 and 390 px, plus the mockup itself in both themes, into
  `test-results/screens/` (gitignored), and fails on a console error, a failed request, a request
  to a non-local host, or a page wider than its viewport. Each frontend task and the
  finish-check use it.
- Reason: a visual stage needs the same repeatable look at every page in both themes; a script
  on the installed library does it with no new dependency and no lockfile change (a Node 24 /
  npm 11 lock has turned CI red before). Mock mode needs no backend, so every task can run it.
- Alternatives considered: `@playwright/test` with visual snapshots; ad-hoc scripts per task.
- Why rejected: a dependency and baseline images to maintain for a one-off redesign; ad-hoc
  scripts would check different things each time.

### 2026-10-19 — Stage 3 stays Tier 2, frontend only, no new dependency
- Decision: no backend, API, schema or hosting change; no new runtime or dev dependency, no
  CSS-in-JS, no UI library, no token build step — `tailwind.config.js` stays the single token
  source and `palette.test.js` the contrast gate.
- Reason: a visual change to an existing Tailwind app; every need (two themes, fonts, logo,
  thin icons) fits the current tools.
- Alternatives considered: a design-token pipeline (Style Dictionary), Tailwind 4 migration.
- Why rejected: no second consumer of the tokens; Tailwind 4 is a migration of its own
  (PROGRESS.md nits) and not asked for.

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
- Stage 3 (storefront redesign), assumptions taken while planning, 2026-10-19 — correct any that is wrong:
  - ვარაუდი (assumption): the mockup is the home page and the shell only; every other page is
    styled by the designer in the same language (`DESIGN.md` per-page guide), without an owner
    review of each page before it is built. The owner reviews the result at the end.
  - ვარაუდი (assumption): where a mockup value fails WCAG AA (planning estimates: the light
    `line2` border ≈ 1.6:1 and the dark one ≈ 1.6:1 as control borders, the light `goldTxt` on the
    footer background ≈ 4.1:1, the light `gold` as text ≈ 3.1:1), the smallest change that passes
    is used; `DESIGN.md` shows mockup and used values side by side.
  - ვარაუდი (assumption): `public/og-image.png` (the picture in shared links) and PNG icons keep
    the old look; only `favicon.svg` changes. A new og-image needs a PNG render of the new logo —
    the owner decides when.
  - ვარაუდი (assumption): product photos stay on a light tile in the dark theme (Decision Log
    2026-10-19).
  - ვარაუდი (assumption): the mockup's decorative drawings (hero device, diamond frames) are
    used as `aria-hidden` decoration; its words are not.
  - ვარაუდი (assumption): the `theme-color` meta in `index.html` follows the two storefront themes
    (`media="(prefers-color-scheme: …)"`); the admin shares `index.html`, so a phone's browser bar
    on `/admin` takes the same colour — browser chrome, not the panel.
  - ვარაუდი (assumption): `/en` uses the same design; Latin headings and prices render in
    Cormorant Garamond, Georgian in Noto Serif / Sans Georgian.
  - ვარაუდი (assumption): order and password-reset emails keep their current look.
