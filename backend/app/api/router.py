from fastapi import APIRouter
from app.api.v1.dev import router as dev_router
from app.api.v1.turns import router as turns_router
from app.api.v1.read import router as read_router
from app.api.v1.context_blocks import router as blocks_router

api_router = APIRouter()
api_router.include_router(dev_router, prefix="/v1/dev", tags=["dev"])
api_router.include_router(turns_router, prefix="/v1", tags=["turns"])
api_router.include_router(read_router, prefix="/v1", tags=["read"])
api_router.include_router(blocks_router, prefix="/v1", tags=["context"])
