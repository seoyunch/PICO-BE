from fastapi import APIRouter

from app.api.endpoints import auth, health, plan

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(plan.router, tags=["plan"])
