from fastapi import APIRouter

from app.api.endpoints import health, plan

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(plan.router, tags=["plan"])
