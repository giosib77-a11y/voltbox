"""Health-check — აპლიკაციის ვერსია და ბაზასთან კავშირი."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import settings
from app.db.session import get_db
from app.schemas.base import ApiModel

logger = logging.getLogger("voltbox.health")

router = APIRouter(tags=["health"])


class HealthResponse(ApiModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["up", "down"]


@router.get("/health", summary="Service health", response_model=HealthResponse)
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> HealthResponse:
    # ბაზის ცოცხლობას რეალური query-ით ვამოწმებთ და არა pool-ის სტატუსით —
    # pool-ს შეიძლება კავშირი "ჰქონდეს", როცა სერვერი უკვე გაითიშა.
    try:
        await db.execute(text("SELECT 1"))
        database: Literal["up", "down"] = "up"
    except Exception as exc:
        # კლიენტს დეტალს არ ვუბრუნებთ, მაგრამ ლოგში უნდა ჩანდეს —
        # ჩაყლაპული გამონაკლისი health-ჩეკს დიაგნოსტიკურ ღირებულებას უკარგავს
        logger.warning("database health check failed", extra={"extra_fields": {"error": repr(exc)}})
        database = "down"

    return HealthResponse(
        status="ok" if database == "up" else "degraded",
        version=__version__,
        environment=settings.app_env,
        database=database,
    )
