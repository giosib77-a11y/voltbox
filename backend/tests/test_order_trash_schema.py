"""The shape migration 0016 gives `orders` for the admin order trash."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_deleted_at_is_a_nullable_timestamptz_with_no_default(db: AsyncSession) -> None:
    row = (
        await db.execute(
            text(
                """
                select data_type, is_nullable, column_default
                from information_schema.columns
                where table_schema = 'public' and table_name = 'orders'
                  and column_name = 'deleted_at'
                """
            )
        )
    ).one()

    assert row.data_type == "timestamp with time zone"
    assert row.is_nullable == "YES"
    # A default would put every new order straight into the trash.
    assert row.column_default is None


async def test_deleted_at_index_is_partial_on_trashed_rows(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            text(
                """
                select i.indexdef, x.indpred is not null as is_partial,
                       pg_get_expr(x.indpred, x.indrelid) as predicate
                from pg_indexes i
                join pg_class c on c.relname = i.indexname
                join pg_namespace n on n.oid = c.relnamespace and n.nspname = i.schemaname
                join pg_index x on x.indexrelid = c.oid
                where i.schemaname = 'public' and i.tablename = 'orders'
                  and i.indexname = 'ix_orders_deleted_at'
                """
            )
        )
    ).all()

    assert len(rows) == 1
    assert rows[0].is_partial
    assert rows[0].predicate == "(deleted_at IS NOT NULL)"
    assert "(deleted_at)" in rows[0].indexdef
