from fastapi import APIRouter

from app.features.imports.routes.documents import router as documents_router
from app.features.imports.routes.mapping import router as mapping_router
from app.features.imports.routes.review import router as review_router

router = APIRouter(tags=["imports"])
router.include_router(documents_router, prefix="/imports")
router.include_router(mapping_router, prefix="/imports")
router.include_router(review_router, prefix="/imports")
