"""Admin dashboard endpoint.

What it does: one request returning every figure the overview page shows.
Where it fits: a thin route over services/dashboard.py.
Notes: the service computes everything with SQL aggregates. Nothing loads orders
into Python to add them up.
"""

from fastapi import APIRouter

from app.core.deps import Db
from app.schemas.admin_orders import DashboardOut
from app.services import dashboard

router = APIRouter(tags=["admin"])


@router.get("/dashboard", summary="Dashboard metrics", response_model=DashboardOut)
async def read_dashboard(db: Db) -> DashboardOut:
    return DashboardOut.model_validate(await dashboard.build(db))
