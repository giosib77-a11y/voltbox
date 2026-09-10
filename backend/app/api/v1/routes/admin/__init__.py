"""Admin API router.

What it does: assembles every admin endpoint under one router that carries
`Depends(require_admin)` at the router level.
Where it fits: mounted by app/api/v1/router.py under the v1 prefix, so the full
path is /api/v1/admin/...

Why the dependency lives on the router and not on each endpoint: a new endpoint
added to any sub-router is protected the moment it is included. Per-endpoint
dependencies are one forgotten decorator away from a public write endpoint, and
tests/test_admin_auth.py enumerates the router to prove nothing slips through.
"""

from fastapi import APIRouter, Depends

from app.api.v1.routes.admin import (
    brands,
    categories,
    dashboard,
    images,
    inventory,
    me,
    orders,
    products,
)
from app.core.deps import require_admin

admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

admin_router.include_router(me.router)
admin_router.include_router(categories.router)
admin_router.include_router(brands.router)
admin_router.include_router(products.router)
admin_router.include_router(images.router)
admin_router.include_router(orders.router)
admin_router.include_router(inventory.router)
admin_router.include_router(dashboard.router)

__all__ = ["admin_router"]
