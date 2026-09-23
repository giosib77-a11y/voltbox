"""Health-check — ორი endpoint, ორი განსხვავებული კითხვა.

`/health/live` — "პროცესი ცოცხალია?" ბაზას არ ეხება. მას Render-ის Health Check
Path და Dockerfile-ის HEALTHCHECK იყენებს: ჩავარდნაზე ორივე instance-ს
რესტარტავს (Render deploy-საც აუქმებს), ბაზის გათიშვას კი რესტარტი ვერ უშველის
— მხოლოდ ცოცხალ instance-ებს დაარტყამდა მარყუჟში.

`/health` — "კლიენტს მოემსახურება?" ბაზის გათიშვისას 503-ს აბრუნებს, რადგან
uptime-მონიტორი მხოლოდ სტატუს-კოდს უყურებს; 200 + "degraded" მისთვის ცოცხალია.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import settings
from app.db.session import get_db
from app.schemas.base import ApiModel

logger = logging.getLogger("voltbox.health")

router = APIRouter(tags=["health"])


class LivenessResponse(ApiModel):
    status: Literal["ok"]
    version: str


class HealthResponse(ApiModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["up", "down"]


@router.get("/health/live", summary="Process liveness", response_model=LivenessResponse)
async def health_live() -> LivenessResponse:
    return LivenessResponse(status="ok", version=__version__)


@router.get(
    "/health",
    summary="Service health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(
    db: Annotated[AsyncSession, Depends(get_db)], response: Response
) -> HealthResponse:
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
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if database == "up" else "degraded",
        version=__version__,
        environment=settings.app_env,
        database=database,
    )
