from fastapi import APIRouter

from app.web.features.foundation.routes import router as foundation_router

router = APIRouter()
router.include_router(foundation_router)
