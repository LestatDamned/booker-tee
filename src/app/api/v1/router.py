from fastapi import APIRouter

from app.api.v1.session.router import router as session_router

router = APIRouter(prefix="/v1")
router.include_router(session_router)
