-- Migration 0015 -> 0016: orders.deleted_at (the admin order trash)
--
-- For the Supabase SQL Editor. Run it by hand on the live database; nothing in the repo runs it.
--
-- Generated offline (connects to nothing) from backend/ at commit a2d3ac1:
--   VOLTBOX_NO_DOTENV=1 JWT_SECRET=<any 32+ characters> \
--   DATABASE_URL=postgresql://voltbox:voltbox@localhost:55432/voltbox \
--   .venv/Scripts/alembic.exe upgrade 0015:0016 --sql
-- then every table name hand-qualified with `public.` (Supabase has its own `auth.*` tables,
-- including `auth.refresh_tokens`; alembic emits `alembic_version` unqualified) and
-- `WHERE alembic_version.version_num` shortened to `WHERE version_num` (same meaning).
--
-- Before: the live head must be 0015 (`select version_num from public.alembic_version;`).
--
-- Statements between BEGIN and COMMIT: 3
--   1. ALTER TABLE ... ADD COLUMN deleted_at   (nullable, no default: every existing order stays live)
--   2. CREATE INDEX ix_orders_deleted_at       (partial: only rows with a timestamp)
--   3. UPDATE public.alembic_version           (checks version_num = '0015')
-- The last UPDATE checks the old value, so on a wrong head it updates 0 rows: the SQL Editor
-- must show `UPDATE 1` for it. If it shows `UPDATE 0`, the head was not 0015 - do not go on.
--
-- Checks after:
--   select version_num from public.alembic_version;
--     -> 0016
--   select data_type, is_nullable from information_schema.columns
--     where table_schema = 'public' and table_name = 'orders' and column_name = 'deleted_at';
--     -> timestamp with time zone | YES
--
-- No new table, so no row level security to enable.

BEGIN;

ALTER TABLE public.orders ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX ix_orders_deleted_at ON public.orders (deleted_at) WHERE deleted_at IS NOT NULL;

UPDATE public.alembic_version SET version_num='0016' WHERE version_num = '0015';

COMMIT;
