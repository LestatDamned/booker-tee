from fastapi import APIRouter

from app.features.imports.routes.documents import router as documents_router

router = APIRouter(tags=["imports"])
router.include_router(documents_router, prefix="/imports")
