"""Admin inventory endpoints.

What it does: the stock overview, manual adjustments and a product's movement
history.
Where it fits: thin routes over services/inventory.py.
Notes: adjustments go through adjust_stock like every other stock change, so
they land in the ledger. System reasons (order_placed, initial) cannot be
selected here - writing one by hand would claim an order caused a change that
no order caused.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import ColumnElement, func, or_, select

from app.core.config import settings
from app.core.deps import AdminUser, Db
from app.core.errors import NotFoundError
from app.db.models import Product
from app.schemas.admin_orders import InventoryPage, InventoryRow, MovementPage
from app.schemas.admin_product import StockAdjustRequest
from app.services import audit, inventory

router = APIRouter(prefix="/inventory", tags=["admin"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _row(product: Product) -> InventoryRow:
    return InventoryRow(
        product_id=product.id,
        name=product.name,
        sku=product.sku,
        stock=product.stock,
        low_stock_threshold=product.low_stock_threshold,
        stock_status=inventory.stock_status(product.stock, product.low_stock_threshold),
    )


@router.get("", summary="Stock overview", response_model=InventoryPage)
async def list_inventory(
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.default_page_size,
    q: str | None = None,
    only: Annotated[str | None, Query(description="low | out")] = None,
) -> InventoryPage:
    # Annotated explicitly: the list starts with an `is_(None)` comparison, so
    # mypy would infer BinaryExpression and reject the `or_(...)` added below.
    conditions: list[ColumnElement[bool]] = [Product.archived_at.is_(None)]
    if only == "low":
        conditions.append(Product.stock <= Product.low_stock_threshold)
    elif only == "out":
        conditions.append(Product.stock <= 0)
    if q and q.strip():
        needle = q.strip()
        conditions.append(
            or_(Product.name.ilike(f"%{needle}%"), Product.sku.ilike(f"{needle.upper()}%"))
        )

    total = await db.scalar(select(func.count()).select_from(Product).where(*conditions))
    products = (
        (
            await db.scalars(
                select(Product)
                .where(*conditions)
                .order_by(Product.stock, Product.name)
                .limit(limit)
                .offset((page - 1) * limit)
            )
        )
        .unique()
        .all()
    )

    total_count = int(total or 0)
    return InventoryPage(
        items=[_row(product) for product in products],
        total=total_count,
        page=page,
        total_pages=(total_count + limit - 1) // limit if limit else 0,
        limit=limit,
    )


@router.post("/{product_id}/adjust", summary="Adjust stock", response_model=InventoryRow)
async def adjust(
    request: Request, db: Db, admin: AdminUser, product_id: UUID, payload: StockAdjustRequest
) -> InventoryRow:
    inventory.validate_manual_adjustment(payload.reason, payload.note)
    await inventory.adjust_stock(
        db,
        product_id,
        payload.change,
        payload.reason,
        actor_id=admin.id,
        note=payload.note,
    )
    await audit.record(
        db,
        actor_id=admin.id,
        action="inventory.adjust",
        entity_type="product",
        entity_id=str(product_id),
        changes={"change": payload.change, "reason": payload.reason},
        ip=_client_ip(request),
    )
    await db.commit()

    product = await db.get(Product, product_id)
    if product is None:  # pragma: no cover - adjust_stock already proved it exists
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    return _row(product)


@router.get("/{product_id}/movements", summary="Stock history", response_model=MovementPage)
async def movements(
    db: Db,
    product_id: UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.default_page_size,
) -> MovementPage:
    rows, total = await inventory.movement_history(
        db, product_id, limit=limit, offset=(page - 1) * limit
    )
    return MovementPage(
        items=rows,
        total=total,
        page=page,
        total_pages=(total + limit - 1) // limit if limit else 0,
        limit=limit,
    )
