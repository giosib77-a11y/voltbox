"""v1-ის ყველა მარშრუტის შეკრება ერთ router-ში."""

from fastapi import APIRouter

from app.api.v1.routes import health

api_router = APIRouter()
api_router.include_router(health.router)
