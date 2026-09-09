"""v1-ის ყველა მარშრუტის შეკრება ერთ router-ში."""

from fastapi import APIRouter

from app.api.v1.routes import catalog_meta, health, products, search

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(catalog_meta.router)
api_router.include_router(search.router)
api_router.include_router(products.router)
