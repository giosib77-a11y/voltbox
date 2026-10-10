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
Stage 1 — Audit fixes (see PROGRESS.md).

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
- Fix the confirmed critical and should-fix findings of the 2026-10-10 audit.
- Keep the existing behaviour, stack and conventions.

### Out of scope (for now)
- Online payment (cash on delivery only — ASSUMPTIONS §4.6).
- Delivery outside Tbilisi and Rustavi (ASSUMPTIONS §4.5).
- New features from ROADMAP P2/P3 (wishlist, reviews UI, promo codes, ...).
- Migrating stack, ORM, router or styling.

## Core Flows
1. Browse catalogue → filter / search (server-side, facets) → product page.
2. Cart in the browser; for a signed-in customer also saved on the server.
3. Checkout (guest or customer) → `POST /orders` with a mandatory
   `Idempotency-Key` → server prices every line from the database, decrements
   stock and writes inventory movements in one transaction → order number
   `VB-...`; Telegram notice to the owner; email confirmation when email is
   configured. (Checkout writes no status-history row today; migration 0004
   backfilled a `pending → pending` start row for older orders — PROGRESS.md.)
4. Admin moves the order through the status machine; cancellation returns stock.
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
- **Order size** (decided 2026-10-10, not yet in code — PROGRESS T12): at most 20 distinct
  products per order and 10 units of each.
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

## Data
PostgreSQL, Alembic migrations `backend/alembic/versions/0001`–`0014`.
- Catalogue: `categories` (tree, `filters` config), `brands`, `products`
  (price, old price, stock, specs JSONB, `search_text`, `name_en`,
  `archived_at`), `product_images`.
- Customers: `users` (role, token_version, lockout counters), `addresses`,
  `carts` (one JSONB cart per account), `refresh_tokens` (families),
  `password_reset_tokens` (one per account, SHA-256 only).
- Orders: `orders` (snapshot of contact and delivery, totals, idempotency key,
  guest `lookup_token_hash`), `order_items` (price and name snapshot),
  `order_status_history`.
- Audit: `inventory_movements`, `admin_audit_log` — no retention (ASSUMPTIONS §8.15).
- Retention: `refresh_tokens` pruned 7 days after expiry by
  `scripts/prune_refresh_tokens.py` (cron job removed while on the free plan).

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
- Rate limits per client IP (`app/core/rate_limit.py`): auth 5/min, guest order
  lookup 10/min, client error reports 20/min, everything else 60/min; password
  reset also 3/hour per email address. Redis-backed in production; client IP
  only through `FORWARDED_ALLOW_IPS` (never `*`).
- Production startup refuses unsafe config (CORS `*`, missing
  `TRUSTED_HOSTS`/`FORWARDED_ALLOW_IPS`, short `JWT_SECRET`, ...).
- Every new table must enable RLS in its migration — the Supabase API is
  public, and a table without RLS is readable through it with the anon key.

## Accepted Risks
- **Sessions last 30 minutes on onrender.com** (owner, 2026-10-10). Storefront and API are
  different sites there (`onrender.com` is on the Public Suffix List), so the
  `SameSite=strict` refresh cookie cannot cross; admin and customers sign in again after
  30 minutes. Ends with `voltbox.ge` + `api.voltbox.ge`. Not accepted: logout failing to
  revoke or reuse detection not persisting — those are T1/T3.

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
- Live Supabase: is the database at migration `0014`? (RLS is on 15/15 tables there per
  the advisor, although no migration enables it on `carts` / `alembic_version` — T2.)
