# VoltBox — Admin Panel: Autonomous Implementation Brief

You are a senior full-stack engineer joining the VoltBox project. Your task is to add a production-grade admin panel to an existing e-commerce monorepo. **Run the whole plan end to end in one go — Setup, then Phase 0 through Phase 4 — without waiting for my approval between phases.** I won't review each step, so your own checks are the safety net. This code will manage real prices, stock and customer orders: correctness and data integrity matter more than speed.

If the original planning document is available (e.g. `docs/voltbox_admin_panel_plan.md`, written in Georgian), read it for background. Where it differs from this brief, this brief wins.

---

## Setup (do this first)

1. **Save this brief in the repo** as `docs/admin-brief.md`. If I dropped it somewhere else in the repo, move it there; if it only exists in the chat, write it there verbatim. This is a long run and your context will be compacted — this file is your source of truth.
2. **Check the working tree (first run only).** If there are uncommitted changes that aren't yours, stop and tell me. Don't commit, stash or discard my work.
3. **Create a branch** `feature/admin-panel` from the current branch and do all work there.
4. **Create `docs/admin-progress.md`**, the state of the run, with these sections: Current phase · Done · Discovery · Decisions to review · Open items · Last check results. Update it after every completed task, not only at the end of a phase.
5. **Resuming:** if the run was interrupted (for example by a usage limit), you are restarted, or I write "გააგრძელე": skip Setup, read `docs/admin-progress.md` and `docs/admin-brief.md`, and continue exactly where the progress file says. Uncommitted changes on `feature/admin-panel` are yours from the interrupted run — compare them with the progress file, finish or redo that task, run its checks, then carry on. Don't redo finished work.

---

## Autonomous run rules

- **Don't stop between phases.** Don't end your turn after a phase and don't ask "should I continue?". When a phase passes its gate, print a short status in Georgian (what was done, what's next) and immediately start the next phase.
- **Phase gate.** A phase is finished only when all its tasks are done, all checks are green (see "Checks"), `docs/admin-progress.md` is updated and the work is committed. Never start a phase on top of a red build.
- **Re-read before each phase.** At the start of every phase, re-read that phase's section of `docs/admin-brief.md` and the progress file. If your context was compacted, also re-read "Communication", "Code documentation" and "Non-negotiable rules".
- **Decide, record, continue.** When something is unclear, choose the most conservative option that keeps every rule, leave a `TODO(voltbox):` in the code if relevant, add an entry under "Decisions to review" (what you chose, why, the alternatives) and keep going. Don't stop for a question you can reasonably answer yourself.
- **Stop only for real blockers**, and update the progress file first:
  - uncommitted changes that aren't yours (first run only — on `feature/admin-panel` after an interruption they are yours);
  - the database you would run migrations or tests against isn't clearly local or test — never touch a remote or production database;
  - a check you can't get green after several genuinely different attempts without breaking a rule;
  - a Phase 0 finding shows the plan doesn't fit the codebase and needs a fundamentally different approach;
  - the task would require breaking a non-negotiable rule, a destructive operation on real data, or secrets you don't have and can't work around.

  When you stop, explain in Georgian what blocked you, what you tried and exactly what you need from me.
- **Not blockers:** missing Supabase credentials (build against the in-memory fake storage and record it), pre-existing lint noise in files you don't touch (baseline it and record it), minor ambiguity in this brief (decide and record).
- **Git.** Small logical commits with English messages (e.g. `feat(admin): add inventory service`). Finish each phase with a commit whose message starts with `phase N:`. Never push, never force-push, never rewrite history, never run `git reset --hard` or `git clean`, never delete branches, never commit `.env` files or secrets.
- **Environment.** Nothing runs against production. No `DROP` / `TRUNCATE` except on a disposable test database. Install only the dependencies this brief allows.
- **Finish with the final report** described at the end of this brief.

---

## Communication

- Talk to me in Georgian: status updates, explanations, decisions, blocker messages and the final report.
- Keep technical terms, code identifiers, file paths, commands, package names and error messages exactly as they are — don't translate them.
- After each set of changes, tell me briefly (in Georgian) which files you changed and what each change does.
- Everything that goes into the repo is English: code comments and docstrings, commit messages, `docs/` files, API field names. The only exception is admin UI text (labels, messages, errors), which is Georgian.

---

## Code documentation — every file explains itself

Every file you create starts with a header that says what the file does and where it fits, so I can understand the code without reading every line.

Python — a module docstring as the first statement:

```python
"""Admin product endpoints: list, create, update, archive, duplicate.

What it does: HTTP layer for managing products from the admin panel.
Where it fits: thin routes over services/catalog.py and services/inventory.py,
protected by require_admin through the admin router.
Notes: stock is never written here after creation; use the inventory endpoints.
"""
```

JavaScript / JSX — a block comment above the imports:

```jsx
/**
 * ProductForm: shared create/edit form for admin products.
 *
 * What it does: renders the product sections, validates input with zod and
 * maps API 422/409 errors to the matching fields.
 * Where it fits: used by the ProductCreate and ProductEdit pages; talks to adminApi.
 * Notes: stock is editable only on create; on edit it links to Inventory.
 */
```

- Every public function, class, React component and hook gets a short docstring or JSDoc saying what it does, plus why when that isn't obvious. If ruff's pydocstyle rules are enabled, follow their format.
- Inside functions, comment the non-obvious *why* (lock ordering, the flush before setting a new primary image, timezone boundaries). Don't narrate what the code already says.
- Alembic migrations: the docstring says what changes in the schema and why. Test modules: the docstring says which behavior they cover.
- Keep headers true: when a file's job changes, update its header in the same commit. If a file you're modifying has no header, add one. Don't edit files you aren't otherwise changing just to add headers.

---

## Engineering rules

- Read the relevant code before changing it. Existing conventions (naming, error format, pagination shape, session handling, test fixtures) beat the suggestions in this brief; record notable deviations under "Decisions to review".
- Never delete or weaken existing tests, never add blanket `# type: ignore` / `eslint-disable`, never loosen lint, type or CI configuration to get a green build.
- Stay in scope: no unrelated refactors. Bugs you find outside the task go under "Open items", not into a silent fix.

### Checks (run before every phase gate)
Use the exact commands from `.github/workflows/`: ruff, mypy, pytest; `alembic upgrade head` on a fresh test database plus `downgrade -1` → `upgrade head` for every new migration; frontend lint and tests (from Phase 1 on); frontend builds in both `mock` and `http` modes. Record the real summary lines in the progress file. Never claim a check passed if you didn't run it; if the environment can't run something, record that.

---

## Non-negotiable rules

These apply in every phase. If one of them blocks you, that's a real blocker: stop and ask instead of working around it.

### Security
- **Authorization lives in the backend.** Every admin endpoint hangs off one `APIRouter` declared with `dependencies=[Depends(require_admin)]`, so a newly added endpoint can't be left unprotected by accident. Frontend guards are UX only.
- **`require_admin` checks the database on every request** (`is_active` and `role == admin`), not only a JWT claim — otherwise a demoted or blocked admin keeps access until the token expires.
- **Nobody becomes admin through the public API.** Registration always creates a `customer` and never accepts `role`. Admins are created with a CLI command.
- **Explicit response models everywhere.** Never return ORM objects directly; that is what keeps `password_hash`, token hashes and internal fields out of responses. Admin input schemas use `extra="forbid"`, so client mistakes fail with 422 instead of being silently ignored.
- **Whitelist sorting and filtering.** Never interpolate user input into SQL or pass raw column names to `order_by`.
- **No secrets in the frontend.** The Supabase service key stays on the backend.

### Data integrity
- **Stock changes only through one inventory service function.** It locks the product row, rejects a negative result, updates `stock` and inserts an `inventory_movements` row, all inside the caller's transaction. This includes the existing checkout. After a product is created, no form or endpoint writes `stock` directly — otherwise the movement history is incomplete from day one.
- **Order status changes only through the state machine** (Phase 3). No endpoint writes arbitrary status values.
- **Products are never hard-deleted.** Order items reference them (`ON DELETE RESTRICT`) and order history must survive. Products are retired by archiving.
- **Money is `Decimal` / `NUMERIC` end to end**, at most 2 decimal places, never float. The frontend sends money as strings taken straight from form inputs, does no money arithmetic, and displays what the API returns.
- **Time.** Store UTC `timestamptz`. Business-day boundaries ("today", date filters) are computed in `STORE_TIMEZONE` (default `Asia/Tbilisi`).
- **Every schema change is an Alembic migration with a working downgrade.** Never edit a migration that has already been applied.

### Accountability
- **Every admin mutation writes an `admin_audit_log` row** (actor, action, entity, before/after of the changed fields) in the same transaction as the change. Inventory adjustments and order transitions have their own history tables — don't double-log those.

### Architecture
- **Admin is an access layer, not a separate domain.** Business rules (inventory, order transitions, slug generation, search-index maintenance) live in domain services shared by storefront and admin. Admin-only code is limited to routes, schemas and admin-specific queries (filtered listings, dashboard aggregates). Admin code must not duplicate domain logic.

---

## Project context (verify in Phase 0 — don't trust blindly)

**Monorepo**
- `frontend/` — React 18, Vite, Tailwind, React Router. All data access goes through `src/services/api.js`, which switches between `mockApi` and `httpApi`. CI builds both modes.
- `backend/` — Python 3.14, FastAPI, SQLAlchemy 2, PostgreSQL, Alembic. Layering: routes → services → db/models. ~110 pytest tests. CI: ruff → mypy → pytest → Alembic migration check → Docker build.

**Reportedly in place**
- `Product`: name, slug, sku, price, old_price, stock, category, brand, specs (JSON), tags, rating, reviews_count, is_active, is_featured, is_new, search_text. `ProductImage` with at most one primary image per product. DB checks: price >= 0, stock >= 0, rating 0-5.
- `categories.filters` (JSONB) drives storefront filtering.
- Checkout reads prices from the DB (client prices are ignored), locks product rows with `SELECT ... FOR UPDATE`, snapshots name/price/image into order items, and supports an `Idempotency-Key` header.
- Auth: Argon2id, hashed refresh tokens, rate-limited login/register, 30-minute access tokens. `users.role` exists (`customer`) but is not enforced anywhere.
- Supabase Storage env vars exist; there is no integration yet.

**Known gaps**
- The frontend never calls `/auth/refresh`, so after 30 minutes users still look logged in but get 401s.
- Checkout doesn't send `Idempotency-Key`.
- No catalog write endpoints, no role enforcement, no frontend lint or tests.

---

## Phase 0 — Discovery (read-only)

Read code and run commands and tests, but don't modify project files (only the Setup files). Record the findings under "Discovery" in the progress file:

1. Every discrepancy between "Project context" and the actual code (fields, constraints, indexes, names).
2. `users.role`: column type (native PG enum, varchar + check, other) and current values; how `get_current_user` works, and whether it loads the user from the DB and checks `is_active`.
3. Order statuses: exact values and how they're stored. If it's a native PostgreSQL ENUM, note it — adding values needs `ALTER TYPE ... ADD VALUE`, which has transaction restrictions (see Alembic's `autocommit_block`).
4. Token handling: where the frontend keeps the access and refresh tokens, whether refresh tokens rotate, whether reuse is detected. If the refresh token is readable from JavaScript, record it as a risk (an admin panel raises the cost of any XSS). Don't change the mechanism in this run.
5. The exact JSON structure of `categories.filters`, every place that reads it (backend filtering and storefront UI), and how filter keys relate to product `specs` keys.
6. How `search_text` / search indexing is maintained (trigger, generated column or application code).
7. The checkout flow in detail: transaction boundaries, the order in which product rows are locked, how idempotency is implemented, whether inactive products are rejected.
8. `product_images`: the ordering field, and how "one primary per product" is enforced (partial unique index?).
9. API conventions: route prefix, pagination response shape, error format, Decimal serialization, how the frontend switches between `mock` and `http`.
10. Whether a reviews table exists and how `rating` / `reviews_count` are computed.
11. Anything in this brief that is wrong for this codebase. If a better alternative stays within the rules and the scope, use it and record why.

Then adapt the later phases to what you found (each adaptation goes under "Decisions to review") and continue. Stop only if a finding is a real blocker.

**Gate:** findings recorded -> commit `phase 0: discovery notes` -> status in Georgian -> continue to Phase 1.

---

## Phase 1 — Foundations

### 1.1 Frontend token refresh
- Implement it in the shared HTTP client (http mode), so storefront and admin both get it.
- On a 401 from a non-auth endpoint, call `/auth/refresh` **once**: all concurrent failing requests await the same in-flight promise (single-flight), then each original request is retried exactly once.
- Never refresh in response to a 401 from `/auth/login` or `/auth/refresh` itself.
- If the refresh fails: clear the session and redirect to the relevant login page (`/admin/login` under `/admin`, the storefront login elsewhere), keeping the return path.
- **Done when:** a test shows three simultaneous 401s cause exactly one refresh call and three successful retries, and a failed refresh logs out with no retry loop.

### 1.2 Checkout `Idempotency-Key`
- Generate the key on the first submit of a checkout attempt (`crypto.randomUUID()`, with a fallback for non-secure contexts such as testing over LAN http) and reuse it for every retry of that attempt: timeouts, network errors, double clicks. Create a new key only after a successful order or when the cart, address or payment choice changes. A new key per click defeats the purpose.
- Disable the submit button while the request is in flight. Handle the backend's replay/conflict responses the way it implements them.
- **Done when:** tests show retries reuse the key and a changed cart gets a new one.

### 1.3 Admin authorization (backend)
- A `require_admin` dependency and an `admin_router` mounted at `/admin` under the existing API prefix (e.g. `/api/v1/admin`), with the router-level dependency.
- `GET /admin/me` returns the current admin's profile (used by the admin shell).
- **Generic protection test:** enumerate every route under the admin prefix from `app.routes`, call each method with dummy path params, and assert: no token -> 401 (if the existing security scheme returns 403 for missing credentials, record it), active customer -> 403, inactive admin -> rejected. The test must cover future endpoints automatically.
- Registration hardening test: registering with `"role": "admin"` yields a `customer` (or a 422).
- CLI (reuse existing tooling if any, otherwise `argparse`): `create-admin --email` (password via `getpass` or an env var — never a CLI argument, it ends up in shell history), `promote-user --email`, `demote-user --email`. Demoting revokes the user's refresh tokens. Document it in the README.

### 1.4 Frontend tooling
- Add ESLint (including `react-hooks` rules) and Vitest + React Testing Library; add lint and tests to the frontend CI job.
- Fix violations that are real bugs. For pre-existing style violations in files you don't touch, baseline them instead of mass-reformatting, and record that.

### 1.5 Admin shell (frontend)
- `/admin/*` routes are lazy-loaded (`React.lazy` + `Suspense`) so admin code ships as a separate chunk, not in the storefront bundle. Confirm it in the build output.
- `/admin/login` uses the existing login endpoint. If the account isn't an admin, show a "no access" message instead of entering the panel.
- `RequireAdmin`: loading -> spinner (no flash, no redirect loop); anonymous -> `/admin/login?next=...`; logged-in non-admin -> 403 page with a link back to the store; admin -> render.
- `AdminLayout`: sidebar with only the sections that exist so far (no dead links), header with the admin's name and logout.
- An `adminApi` module on top of the same HTTP client (auth header + refresh). The admin is **http-only**: in `mock` mode, `/admin` shows a notice that it needs the backend, and the mock build must still compile. Don't duplicate admin endpoints in `mockApi`.
- Dependencies you may add (record why for each): frontend `@tanstack/react-query`, `react-hook-form`, `zod`, `@hookform/resolvers`, plus the ESLint/Vitest/Testing Library dev packages; backend `Pillow`, plus `httpx` or the official `supabase` client for storage. Nothing else — if something else seems necessary, record it under "Decisions to review" and work without it.
- **Done when:** `RequireAdmin` tests cover all four states and the admin chunk is separate.

**Gate:** checks green (now including frontend lint and tests) -> commit `phase 1: foundations` -> status in Georgian -> continue to Phase 2.

---

## Phase 2 — Catalog

### 2.1 Migrations
- `products.low_stock_threshold` INT NOT NULL DEFAULT 5, CHECK >= 0 (if missing).
- `products.archived_at` TIMESTAMPTZ NULL. `is_active = false` means temporarily hidden (draft, out of season); archived means retired. Archiving sets `archived_at` **and** `is_active = false`, so storefront queries need no change. Archived products are excluded from default admin lists and can't be activated until unarchived (409). The original plan mapped both "Deactivate" and "Archive" to `is_active = false`, which made them the same button.
- `inventory_movements`: id, product_id FK, change INT NOT NULL CHECK (change <> 0), previous_stock INT, new_stock INT with CHECK (new_stock = previous_stock + change AND new_stock >= 0), reason, note TEXT NULL, order_id FK NULL, created_by FK users NULL (NULL = system/checkout), created_at; index on (product_id, created_at DESC). Reasons: `initial`, `restock`, `manual_adjustment`, `order_placed`, `order_cancelled`, `return`, `correction` — store them as VARCHAR + CHECK (or the project's existing enum convention), not a native PG enum, so adding a reason later is easy.
- Backfill one `initial` movement for every existing product with stock > 0, so the ledger matches current stock from the start.
- `admin_audit_log`: id, actor_id FK users, action (e.g. `product.update`), entity_type, entity_id TEXT, changes JSONB (`{"field": [old, new]}`), ip NULL, created_at; indexes on (entity_type, entity_id) and (created_at).

### 2.2 Inventory service + checkout integration
- `adjust_stock(session, product_id, change, reason, *, actor_id=None, order_id=None, note=None)`: lock the product row, compute, raise a domain error if the result would be negative (-> 409 in admin APIs), update, insert the movement. It doesn't commit.
- Route checkout's stock decrement through it (`order_placed`, one movement per item) **without changing checkout behavior**: prices from the DB, locking, snapshots, idempotency. Lock product rows in a consistent order (ascending id) so two concurrent orders can't deadlock; if checkout already does this, keep it. All existing tests must pass unchanged; add tests for the movements.
- Checkout must reject inactive and archived products (add it with a test if missing). Once admins can switch products off, a product can disappear while it sits in someone's cart.

### 2.3 Categories and brands API
- **Categories:** list (with parent_id, position, product and child counts), get, create, patch, delete.
  - Validate `filters` with a Pydantic model that matches **exactly** the structure found in Phase 0. Don't invent a new format — the storefront must keep working.
  - Reject self-parenting and cycles (walk the ancestors); respect the nesting depth the storefront supports.
  - Delete -> 409 with counts if the category has products or children; otherwise allowed. The UI's default action is deactivate.
- **Brands:** list (product counts via one aggregate query, no N+1), get, create, patch, delete (409 if it has products).
- **Shared slug utility:** generated from the name when empty, `[a-z0-9-]`, unique (409 on conflict). Georgian is transliterated with an explicit map (national romanization, no apostrophes): ა a, ბ b, გ g, დ d, ე e, ვ v, ზ z, თ t, ი i, კ k, ლ l, მ m, ნ n, ო o, პ p, ჟ zh, რ r, ს s, ტ t, უ u, ფ p, ქ k, ღ gh, ყ q, შ sh, ჩ ch, ც ts, ძ dz, წ ts, ჭ ch, ხ kh, ჯ j, ჰ h. Tests: `ტელეფონები` -> `teleponebi`, `სმარტ საათები` -> `smart-saatebi`, `iPhone 15 Pro` -> `iphone-15-pro`.

### 2.4 Products API
- `GET /admin/products`: pagination (`page`, `page_size` <= 100); search by name (through the existing search infrastructure), SKU (exact/prefix) and slug; filters for category, brand, active, archived (excluded by default), featured, new, low stock and price range; whitelisted sort. Eager-load category, brand and primary image.
- `GET /admin/products/{id}`, `POST /admin/products`, `PATCH /admin/products/{id}` (partial, `exclude_unset`).
- Writable: name, sku, slug, category_id, brand_id, price, old_price, low_stock_threshold, description fields (whatever exists), specs, tags, is_active, is_featured, is_new.
  - Create-only: initial `stock` (writes an `initial` movement).
  - Never writable here: `stock` after creation, `rating`, `reviews_count`, `search_text`, `archived_at`.
- Validation: `old_price` is null or greater than `price`; SKU unique (normalized per the existing convention) -> 409; slug unique -> 409; category and brand exist; `specs` is a flat object with trimmed string keys and string/number/boolean values, size-bounded; tags trimmed, de-duplicated and bounded.
- Actions: `POST /admin/products/{id}/archive`, `POST /admin/products/{id}/unarchive`, `POST /admin/products/{id}/duplicate` (copies content but not images; new unique SKU and slug with a `-copy` suffix; `is_active = false`; stock 0). Activate/deactivate via PATCH `is_active` (409 while archived).
- Search stays in sync: a test proves that a product created or renamed through the admin API is found by the storefront search.

### 2.5 Product images (Supabase Storage)
- Put storage behind an interface (e.g. a `StorageBackend` protocol) with a Supabase implementation and an in-memory fake for tests. If Supabase credentials aren't available, finish everything against the fake and record it.
- Use a **public bucket** for product images. Signed URLs expire, which would break storefront pages and the image URLs snapshotted in orders.
- `POST /admin/products/{id}/images` (multipart): max 5 MB (configurable); JPEG, PNG or WebP only, verified by actually decoding the file with Pillow — never trust the extension or the client's MIME type; cap pixel dimensions (decompression bombs); reject SVG, which can carry scripts. Object key `products/{product_id}/{uuid4}.{ext}`. The first image becomes primary. Re-encoding to strip EXIF is optional.
- `PUT /admin/products/{id}/images/order` with the full ordered list of image ids (must match the product's current set exactly).
- `POST /admin/products/{id}/images/{image_id}/primary`: unset the current primary, **flush**, then set the new one. The one-primary rule (likely a partial unique index) is checked immediately, and SQLAlchemy may reorder UPDATEs within a single flush.
- `DELETE /admin/products/{id}/images/{image_id}`: delete the row; delete the storage object only if no order item snapshot references its URL; if it was primary, promote the next image.
- UI flow: a new product is saved first (inactive by default), then the images section unlocks. This avoids orphaned uploads.

### 2.6 Catalog UI
- **Products list:** thumbnail, name, SKU, category, brand, price, old price, stock (low/out badge), status (active / inactive / archived), featured, new, created, actions. Search, filters, sort and page live in the URL query string, so the back button and shared links work. Search is debounced. Loading, empty and error states all exist.
- **Product form** (create and edit share one `ProductForm`), sections: Basic, Pricing, Inventory (stock editable only on create; on edit, show current stock with a link to the inventory adjustment), Content, Specifications, Flags, Images.
- **Specs editor:** when a category is selected, the spec keys its filters rely on appear as structured fields (with options where the filter defines them), plus free-form rows for extra specs. This stops admins from silently breaking filters with "RAM" vs "Ram".
- Map 422 errors to their fields and 409 conflicts to the relevant field (e.g. duplicate SKU). Warn about unsaved changes (the router's blocker if the router setup supports it, `beforeunload` at minimum). Confirm before archiving. Warn, but don't block, when activating a product without images. Warn when changing the slug of a product that has been live, since old links will break.
- **Categories page:** indented tree with position, activate/deactivate, a create/edit dialog including a filters editor that produces exactly the validated schema.
- **Brands page:** list with product counts, create/edit.

**Gate:** checks green, all pre-existing tests pass unchanged -> commit `phase 2: catalog` -> status in Georgian -> continue to Phase 3.

---

## Phase 3 — Orders, inventory, dashboard

### 3.1 Order state machine
Intended graph (use the existing status values found in Phase 0):
```
pending    -> confirmed | cancelled
confirmed  -> processing | cancelled
processing -> shipped | cancelled
shipped    -> delivered
delivered  -> (terminal)
cancelled  -> (terminal)
```
- Define the transition table once, in the order domain service.
- New table `order_status_history`: order_id, from_status, to_status, changed_by, note, created_at.
- `POST /admin/orders/{id}/status` with `{ "to": "...", "note": "..." }`: lock the order row (`FOR UPDATE`), validate (409 if not allowed), apply side effects, write history and the audit log.
- **Cancellation returns stock:** for each item, `adjust_stock(session, item.product_id, +item.quantity, "order_cancelled", order_id=order.id)` in the same transaction, locking products in ascending id order. Because the order row is locked first, a double cancel can't restock twice — test it.
- The order detail response includes `allowed_transitions`, so the UI never re-implements the state machine.
- Payment: display the existing payment fields only. Don't build payment logic; if a separate payment status seems needed (e.g. cash on delivery collected), record it under "Decisions to review".

### 3.2 Orders API and UI
- List: filter by status and date range (store timezone); search by order number, customer name, email and phone — normalize digits so `+995 555 12 34 56` and `555123456` match; pagination; newest first. Item counts via aggregates, no N+1.
- Detail page: number, created, status badge, customer, phone, city, address, comment; items from snapshots (product, qty, unit price, line total); subtotal, shipping, total, payment method; status history timeline; buttons only for `allowed_transitions`; a cancel confirmation that says stock will be returned.

### 3.3 Inventory API and UI
- `GET /admin/inventory`: product, SKU, stock, threshold, status (ok / low / out); filter by low/out; search.
- `POST /admin/inventory/{product_id}/adjust` with `{ change, reason, note }`. Allowed manual reasons: `restock`, `manual_adjustment`, `return`, `correction`; a note is required for `manual_adjustment` and `correction`.
- `GET /admin/inventory/{product_id}/movements`: paginated history with actor and linked order.
- UI: table with an adjust dialog (+/-, reason, note) and a history panel ("+20 — Restock", "-1 — Order #1023").

### 3.4 Dashboard
- `GET /admin/dashboard`: one request, SQL aggregates only (never load orders into Python). Keep it fast; add indexes if needed (e.g. `orders.created_at`, `orders.status`).
- Definitions, kept as documented constants in code:
  - Sales = sum of order totals **excluding `cancelled`**.
  - Today = 00:00-24:00 in the store timezone.
  - Metrics: sales today, orders today, total sales, count per status, active products (active and not archived), low-stock count (active products with stock <= threshold), top 5 products by quantity over the last 30 days (excluding cancelled, from order item snapshots), 10 latest orders, 5 latest products.
- Test the timezone boundary: an order placed at 01:00 Tbilisi time (21:00 UTC the previous day) counts as today.
- UI: KPI row, status counts linking to the filtered orders list, low-stock list linking to inventory, latest orders.

**Gate:** checks green -> commit `phase 3: orders, inventory, dashboard` -> status in Georgian -> continue to Phase 4.

---

## Phase 4 — Customers

- List: name, email, phone, orders count, total spent (excluding cancelled), created, status; search; pagination; aggregates via subqueries.
- Detail: profile, addresses, order history.
- Block/unblock sets `is_active`; blocking revokes all of the user's refresh tokens. An admin can't block themselves or another admin.
- A test serializes a customer response and asserts that no credential or token fields are present.

**Gate:** checks green -> commit `phase 4: customers` -> write the final report.

---

## Conventions and quality bar

**API**
- Endpoint paths in this brief (`/admin/...`) are relative to the existing API prefix (e.g. `/api/v1`).
- List responses are `{ items, total, page, page_size }` unless the project already has a pagination shape — then use that.
- 401 unauthenticated · 403 not an admin · 404 not found · 409 conflict (duplicate SKU/slug, invalid transition, insufficient stock, blocked delete) · 422 validation. PATCH is partial.

**UI**
- Admin UI text (labels, messages, errors) is Georgian; use the storefront's i18n setup if it has one.
- The admin is a work tool: density, scannability and consistency over decoration. Tables are the main surface. Reuse the storefront's Tailwind theme (colors, fonts) so it still feels like VoltBox, and don't wrap every block in identical shadowed cards.
- Shared primitives: Button, Input, Select, Textarea, Checkbox, Badge, Modal/ConfirmDialog, Toast, DataTable, Pagination, EmptyState.
- Status is shown as text plus color, never color alone. Visible keyboard focus, every input labeled, usable at tablet width.
- Consistent wording: if the button says "შენახვა", the toast says "შენახულია". Errors say what happened and how to fix it; empty states point to the next action.
- Money: `Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' })`. Dates: `Intl.DateTimeFormat('ka-GE', { timeZone: 'Asia/Tbilisi', dateStyle: 'medium', timeStyle: 'short' })`.

**Tests (minimum)**
- Backend: the generic admin protection test; happy path, validation and conflict cases for every endpoint; an exhaustive state-machine test over all (from, to) pairs; cancel restocks and a double cancel doesn't; stock never goes negative; two concurrent adjustments of the same product serialize correctly; checkout writes movements; image validation against the fake storage; the dashboard timezone boundary; audit rows are written.
- Frontend: `RequireAdmin` states, refresh single-flight, idempotency key reuse, `ProductForm` validation and server-error mapping.

**Docs**
- Every new or changed file has an accurate header and docstrings (see "Code documentation").
- README: creating the first admin, env vars (Supabase URL/key/bucket, `STORE_TIMEZONE`), bucket setup (public read, backend-only write), running the admin locally.

---

## Final report (in Georgian, at the very end)

1. Summary of each phase
2. Decisions to review — most important first
3. Open items and TODOs, including anything built against fakes (e.g. Supabase)
4. Risks and known limitations
5. How to try it, step by step: apply migrations, create the first admin, set env vars, open `/admin`
6. Check results — the actual summary lines from ruff, mypy, pytest (with test count), eslint, vitest and both builds
7. Git: the branch name and the list of phase commits

---

## Out of scope (don't build)

Reports beyond the dashboard, CSV export, bulk actions, review moderation, coupons/discounts/promotions, multiple admin roles and permissions, a settings page, a standalone media library, notifications, abandoned carts, returns/refunds, 2FA, payment integrations. Keep RBAC possible later (`require_admin` can grow into `require_permission(...)`), but don't build it now.

---

**Start now: do the Setup, then Phase 0, and keep going without stopping until Phase 4 has passed its gate and the final report is written.**
