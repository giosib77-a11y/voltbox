-- Migration 0016 -> 0017: orders.request_hash (AUDIT.md A-042, an Idempotency-Key reused with a different cart)
--
-- For the Supabase SQL Editor. Run it by hand on the live database BEFORE deploying the code that
-- carries migration 0017 (the new code writes and reads orders.request_hash; without the column every
-- checkout fails). Nothing in the repo runs it.
--
-- Generated offline (connects to nothing) from backend/:
--   VOLTBOX_NO_DOTENV=1 JWT_SECRET=<any 32+ characters> \
--   DATABASE_URL=postgresql://voltbox:voltbox@localhost:55432/voltbox \
--   .venv/Scripts/alembic.exe upgrade 0016:0017 --sql
-- then `alembic_version` hand-qualified with `public.` (Supabase has its own `auth.*` tables,
-- including `auth.refresh_tokens`; alembic emits `alembic_version` unqualified) and
-- `WHERE alembic_version.version_num` shortened to `WHERE version_num` (same meaning).
--
-- Before: the live head must be 0016 (`select version_num from public.alembic_version;`).
--
-- Statements between BEGIN and COMMIT: 2
--   1. ALTER TABLE ... ADD COLUMN request_hash   (nullable, no default, no backfill: existing orders
--                                                 keep NULL and are compared on the key alone)
--   2. UPDATE public.alembic_version             (checks version_num = '0016')
-- The last UPDATE checks the old value, so on a wrong head it updates 0 rows: the SQL Editor
-- must show `UPDATE 1` for it. If it shows `UPDATE 0`, the head was not 0016 - do not go on.
--
-- Checks after:
--   select version_num from public.alembic_version;
--     -> 0017
--   select data_type, character_maximum_length, is_nullable from information_schema.columns
--     where table_schema = 'public' and table_name = 'orders' and column_name = 'request_hash';
--     -> character varying | 64 | YES
--
-- No new table, so no row level security to enable.

BEGIN;

ALTER TABLE public.orders ADD COLUMN request_hash VARCHAR(64);

UPDATE public.alembic_version SET version_num='0017' WHERE version_num = '0016';

COMMIT;
