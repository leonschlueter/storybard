from fastapi import APIRouter
from app.api.v1 import campaigns, actors, actions

api_router = APIRouter()

api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(actors.router, prefix="/actors", tags=["actors"])
api_router.include_router(actions.router, prefix="/actions", tags=["actions"])


@api_router.get("/health")
def health():
    return {"ok": True}
