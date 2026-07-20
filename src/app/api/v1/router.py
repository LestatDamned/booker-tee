from fastapi import APIRouter

from app.api.v1.manual_ledger.router import router as manual_ledger_router
from app.api.v1.session.router import router as session_router

router = APIRouter(prefix="/v1")
router.include_router(manual_ledger_router)
router.include_router(session_router)
