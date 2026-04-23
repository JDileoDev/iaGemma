"""API v1 endpoints."""

from fastapi import APIRouter
from app.api.v2 import health, informes, importador


api_router = APIRouter(prefix="/api/v2")

# Include all v1 routers
api_router.include_router(informes.router)
api_router.include_router(health.router)
api_router.include_router(importador.router)