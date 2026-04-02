from fastapi import APIRouter

from app.api.routes import agents, health, provider_models, providers, workspaces

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(agents.router, tags=["agents"])
api_router.include_router(
    provider_models.router,
    prefix="/provider-models",
    tags=["provider-models"],
)
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
