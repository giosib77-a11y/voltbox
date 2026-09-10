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

**Phase 2 — Catalog** ✅ complete → starting Phase 3

---

## Done

- [x] Setup 1 — brief saved to `docs/admin-brief.md` (34.7 KB)
- [x] Setup 2 — working tree checked: clean at `fc2b933`, nothing of the user's at risk
- [x] Setup 3 — branch `feature/admin-panel` created from `main`
- [x] Setup 4 — this file created
- [x] Phase 0 — discovery (commit `fe0a02e`)
- [x] 1.4 frontend tooling — eslint 9 flat config + vitest/jsdom/RTL, CI `quality` job
- [x] 1.1 token refresh — `services/session.js` single-flight, retry-once in `request()`
- [x] 1.2 checkout `Idempotency-Key` — `useIdempotencyKey`, sent as a header
- [x] 1.3 backend authorization — `require_admin`, `admin_router`, `GET /admin/me`,
      generic protection test, `scripts/manage_admin.py`
- [x] 1.5 admin shell — `RequireAdmin`, `AdminLayout`, `AdminLogin`, separate chunk
- [x] Phase 1 gate (commit `468bc71`)
- [x] 2.1 migration 0003 — `archived_at`, `inventory_movements`, `admin_audit_log`, backfill
- [x] 2.2 `services/inventory.adjust_stock` — sole write path; checkout + cancel routed through it
- [x] 2.3 categories/brands API, `services/slug.py`, `services/audit.py`
- [x] 2.4 products API — list/get/create/patch/archive/unarchive/duplicate
- [x] 2.5 product images — `StorageBackend` protocol, Supabase + in-memory fake
- [x] 2.6 catalog UI — products list/form, specs editor, images, categories, brands

---

## Discovery

Baseline verified before any change: **110 pytest passed**, ruff `All checks passed!`,
mypy `Success: no issues found in 44 source files`, and `alembic upgrade head` +
`downgrade -1` + `upgrade head` all clean on the local disposable DB.
Supabase confirmed untouched afterwards (6 categories, 0 products).

### 1. Discrepancies with "Project context"

| Brief says | Reality |
|---|---|
| add `low_stock_threshold` DEFAULT 5 "if missing" | **Already exists**, `server_default="3"` (matches the frontend `LOW_STOCK_THRESHOLD`). Do **not** add it or change the default. |
| validation errors are 422 | **Project returns 400.** `register_exception_handlers` deliberately rewrites FastAPI's 422 to 400 because the frontend contract expects it. |
| list responses `{items, total, page, page_size}` | **Project uses `{items, total, page, totalPages, limit, facets}`** (`core/pagination.py`). The query param is `limit`, not `page_size`. |
| `Address.address` | The column is `address_line`. |
| checkout "supports Idempotency-Key" | Correct, and a replay **returns the existing order** rather than a 409. |
| `Product` has `rating`, `reviews_count` | Present, but **there is no reviews table** - they are static seeded columns with no source to recompute from. |

Everything else in "Project context" checked out.

### 2. `users.role` and `get_current_user`

- `role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="customer")`.
  **Plain VARCHAR, no CHECK constraint, no native PG enum.** Adding `"admin"` needs no migration.
- `get_current_user` (`app/core/deps.py`) **already loads the user from the DB and checks
  `is_active`**, so `require_admin` only has to add the role check. The "demoted admin keeps
  access until the token expires" hole does not exist in this codebase.
- `bearer_scheme = HTTPBearer(auto_error=False)`; missing credentials raise `UnauthorizedError`
  -> **401**, not 403. The generic protection test can assert 401.

### 3. Order statuses

- `ORDER_STATUSES = ("pending","confirmed","processing","shipped","delivered","cancelled")`
  in `app/db/models/orders.py`, stored as `String(20)` with a **CHECK constraint**, not a PG enum.
  **No `ALTER TYPE` / `autocommit_block` complexity.** The values match the brief's graph exactly.
- `orders.status` server_default is `"pending"`.

### 4. Token handling

- The frontend keeps the whole session in **`localStorage` under `auth:v1`**:
  `{ user, token, refreshToken, expiresAt }`. Both tokens are readable from JavaScript.
  **Recorded as a risk** (see "Open items"); not changed in this run, per the brief.
- Backend `refresh()` **rotates**: the used token gets `revoked_at` and a new pair is issued.
- **No reuse detection**: replaying a revoked token returns 401 but does not revoke the rest
  of that user's token family. Recorded under "Open items".
- `revoke_all(db, user_id)` **already exists** in `app/services/auth.py` - reuse it for
  `demote-user` (Phase 1.3) and for blocking a customer (Phase 4). No new code needed.

### 5. `categories.filters` structure

```json
[{ "key": "brand",           "label": "ბრენდი", "type": "checkbox" },
 { "key": "specs.ram",       "label": "ოპერატიული მეხსიერება", "type": "checkbox" },
 { "key": "specs.network",   "label": "5G", "type": "toggle", "match": "5G" },
 { "key": "specs.fastCharge","label": "სწრაფი დატენვა", "type": "toggle", "match": true },
 { "key": "specs.color",     "label": "ფერი", "type": "swatch" }]
```

- `key` is `"brand"` or `"specs.<specKey>"` - this is exactly the link to product `specs` keys.
- `type` is one of `checkbox | toggle | swatch`. `match` appears **only** on `toggle` and is
  a string **or** a boolean.
- Read by `app/services/catalog.py` (`param_for`, `collect_conditions`, `compute_facets`) and
  by the frontend `FilterSidebar` / `paramForFilter`.
- `GLOBAL_FILTERS` (category + brand) is the fallback when a category defines none.
- The Pydantic validation model in Phase 2.3 must mirror this exactly - inventing a new shape
  would break the storefront.

### 6. `search_text` maintenance

- **Application code only** - `app.services.search.build_search_text(...)`. No trigger and no
  generated column (deliberate: the value depends on `brands` and `categories` rows, which a
  Postgres generated column cannot see).
- Called today from `scripts/seed.py`, `scripts/import_products.py`, `scripts/reindex_search.py`
  and `tests/factories.py`. **There is no app-layer write path yet**, so every admin write
  endpoint must call it, and it needs the product's `brand.name`, `category.name` and
  `category.slug` loaded.

### 7. Checkout flow

- One transaction. `_lock_products` locks in two steps: `SELECT products.id ... ORDER BY id
  FOR UPDATE`, then a full load. Two steps are required because `Product.brand`/`category`
  are `lazy="joined"` and Postgres refuses `FOR UPDATE` on the nullable side of an outer join.
- **Locking is already ascending by id** - the brief's deadlock requirement is already met; keep it.
- Prices always come from the DB; a client-sent price is impossible (`ApiRequest` forbids extras).
- Stock decrement is a separate atomic `UPDATE ... WHERE stock >= :qty` with a `rowcount != 1` check.
- **Inactive products are already rejected** (`if product is None or not product.is_active`).
  Because archiving will also set `is_active = false`, archived products are covered for free.
- Idempotency: a matching `orders.idempotency_key` returns the existing order.
- `order.cancel()` exists in the service and restocks with a plain `UPDATE`, **but no route
  calls it** - it is currently dead code. Phase 3 will route it through the state machine and
  the inventory service.
- The order-item image snapshot picks `min(position)`, **not `is_primary`**. Minor
  inconsistency, recorded under "Open items".

### 8. `product_images`

- Ordering column is `position` (int, default 0); the relationship uses
  `order_by="ProductImage.position"`.
- One primary per product is enforced by a **partial unique index**
  `uq_product_images_one_primary ON product_images (product_id) WHERE is_primary`.
  The brief's "unset, flush, then set" requirement is therefore real and necessary.
- `ON DELETE CASCADE` from products.

### 9. API conventions

- Prefix `settings.api_v1_prefix` = `/api/v1`; routers assembled in `app/api/v1/router.py`.
- Error envelope: `{"error": {"code": "SCREAMING_SNAKE", "message": "...", "details": ...}}`
  plus an `X-Request-ID` response header.
- `AppError` subclasses: `NotFoundError` 404, `ValidationError` **400**, `UnauthorizedError` 401,
  `ForbiddenError` 403, `ConflictError` 409.
- All schemas derive from `ApiModel` / `ApiRequest` (`app/schemas/base.py`):
  `alias_generator=to_camel`, `populate_by_name=True`; requests **already** set `extra="forbid"`.
- Sorting is already whitelisted through a `SORTABLE` dict of column expressions in
  `app/services/catalog.py` - follow that pattern for admin sorting.
- The frontend picks its implementation at **build time** via `vite.config.js`
  `resolve.alias['virtual:api-impl']`, driven by `VITE_API_MODE`.

### 10. Reviews

- **No reviews table.** `products.rating` (`Numeric(2,1)`, CHECK 0-5) and
  `products.reviews_count` are seeded static values. Keeping them read-only in the admin API
  is correct - there is nothing to recompute them from.

### 11. Things in the brief that do not fit this codebase

1. **422 -> 400** for validation (see §1). Following the project.
2. **`page_size` -> `limit`**, and list responses also carry `totalPages` and `facets` (see §1).
3. **`low_stock_threshold` already exists with default 3.** Not adding it, not changing it.
4. **The frontend has no ESLint/Vitest at all** - devDependencies are only Vite, Tailwind,
   PostCSS and React types. Phase 1.4 starts from zero, so there is no pre-existing lint
   baseline to preserve.
5. **No `STORE_TIMEZONE` setting** in `app/core/config.py` (`currency = "GEL"` does exist).
   `supabase_project_ref` and `supabase_service_role_key` exist but are empty, and there is
   **no bucket setting** - Phase 2.5 must add one.
6. **Scripts parse `sys.argv` by hand**, not argparse (`scripts/import_products.py`). The admin
   CLI needs named options plus `getpass`, so argparse is the better fit; recorded as a decision.

## Decisions to review

Most important first.

1. **Validation errors stay 400, not the 422 the brief asks for.**
   The project rewrites FastAPI's 422 to 400 on purpose (`core/errors.py`) because the
   frontend contract branches on it. The brief says existing conventions win. All other
   codes match the brief (401/403/404/409).

2. **Pagination keeps the project's shape.** `{items, total, page, totalPages, limit, facets}`
   with a `limit` param, not `{items, total, page, page_size}`. Same rule.

3. **`low_stock_threshold` is left at default 3.** It already exists and mirrors the
   frontend's `LOW_STOCK_THRESHOLD`. Changing it to the brief's 5 would silently alter which
   products the storefront shows as low stock.

4. **Migrations run against `voltbox_mig`, a separate local DB.**
   `backend/.env` points at Supabase, so a bare `alembic` command would hit production.
   Every migration command in this run sets `DATABASE_URL` explicitly. Alternative
   considered: temporarily editing `.env` - rejected, too easy to forget to revert.

5. **Admin CLI will use `argparse`,** although existing scripts parse `sys.argv` by hand.
   The CLI needs named options and `getpass`; hand parsing would be worse here. The existing
   scripts are not touched.

6. **`require_admin` adds only a role check.** `get_current_user` already loads the user from
   the DB and verifies `is_active`, so the brief's "check the database on every request"
   requirement is satisfied by composing on top of it rather than duplicating the query.

7. **`low_stock_threshold` left at 3, not the brief's 5.** It already exists and
   mirrors the frontend constant; changing it would silently alter which products
   the storefront shows as low stock.

8. **`clock_timestamp()` for ledger and audit `created_at`.** `now()` is the
   transaction start time, so every movement written by one checkout would share
   a timestamp and the history could not be ordered. Found by a failing test.

9. **Audit snapshots skip `id`, `created_at`, `updated_at`.** Two reasons:
   `updated_at` would appear in the diff of every edit and bury the real change,
   and reading it right after a flush triggers a lazy refresh that raises
   MissingGreenlet under async SQLAlchemy.

10. **An explicit duplicate slug is 409; a generated one gets a suffix.**
    Renaming what the author typed produces a URL they did not choose; when they
    expressed no preference, a suffix is the helpful answer.

11. **Category nesting capped at 2 levels** (`MAX_CATEGORY_DEPTH`). The storefront
    renders one level of children; anything deeper would be unreachable in the UI.

12. **Georgian transliteration collapses aspirated pairs** (თ/ტ → t, ქ/კ → k,
    ფ/პ → p, ჩ/ჭ → ch, ც/წ → ts). The national romanization distinguishes them
    with apostrophes, which cannot appear in a URL.

13. **No `react-hook-form` / `zod`.** The brief allows them, but the storefront
    already validates with `useState` + explicit checks (`Checkout.jsx`). Two
    form paradigms in one codebase costs more than the library saves, and it
    avoids three dependencies. Server errors are mapped to fields by hand in
    `fieldErrorsFrom`.

14. **`lazy()` calls live inside `adminChildren()`**, not at module scope. Since
    `VITE_API_MODE` is substituted at build time, the mock branch is dead code
    and Rollup drops every admin chunk - verified: a mock build contains only
    `AdminUnavailable`.

15. **Money is sent as the typed string**, never parsed in the browser. Parsing
    is how `10.10` becomes `10.099999999999999`. A test asserts it.

16. **`useBlocker` needs a data router**, so ProductForm's tests use
    `createMemoryRouter` + `RouterProvider` rather than `MemoryRouter`.

---

## Open items

Found during discovery, outside this task's scope - not silently fixed.

1. **Refresh tokens have no reuse detection.** Replaying a revoked token returns 401 but does
   not revoke the rest of the family, so a stolen token cannot be detected. `app/services/auth.py`.
2. **Both tokens live in `localStorage`** (`auth:v1`), readable by any script on the page. An
   admin panel raises the cost of any XSS. The brief says not to change the mechanism in this run.
3. **`order.cancel()` is dead code** - implemented but no route calls it. Phase 3 will supersede it.
4. **Order item image snapshots use `min(position)`, not `is_primary`.** If a product's primary
   image is not also position 0, the order shows a different image than the product page.
5. **`rating` / `reviews_count` have no source.** No reviews table; the values are seeded and
   can never be recomputed.

6. **Two more undeclared dependencies found and fixed** (`python-multipart`,
   and `httpx` which was a dev-only extra although `services/storage.py` imports
   it at runtime). Same class as `email-validator`. The `image` CI job now covers
   this, but it only catches import-time failures - a dependency used lazily
   inside a rarely-taken branch would still slip through.

7. **Supabase Storage is not exercised against the real service.** All image
   tests run against `InMemoryStorage`. `SupabaseStorage` is written but has
   never made a live call; the bucket does not exist yet. Creating it (public
   read, backend-only write) is a manual step recorded in the README.

8. **jsdom's `AbortSignal` is not undici's.** When React Router's data router
   navigates after a successful save, it builds a `Request` that Node's fetch
   rejects. It surfaces as an unhandled rejection, not a test failure, but it
   turns the run's exit code into 1. Worked around in the one test that
   navigates; a project-wide fix would need a polyfill in `vitest.setup.js`.

9. **Category `position` is editable but there is no drag-to-reorder.** The
   dialog exposes the number; a nicer control was out of scope.

---

## Last check results

End of Phase 2 (all run locally):

```
ruff        All checks passed!
ruff fmt    87 files already formatted
mypy        Success: no issues found in 62 source files
pytest      274 passed in 42.74s
alembic     0003 upgrade / downgrade -1 / upgrade  -> head    [local voltbox_mig]
            backfill verified against real rows: stock 7/0/41 reconciles exactly
docker      image builds; app imports inside the container, 33 paths
eslint      0 errors, 5 warnings   (react-refresh in Context files - see decisions)
vitest      22 passed (4 files), exit 0
build mock  316.26 kB   (admin fully eliminated - only AdminUnavailable survives)
build http  273.69 kB   (admin ships as 8 separate chunks, largest 17.1 kB)
```
