from fastapi import APIRouter

from app.web.features.foundation.routes import router as foundation_router
from app.web.features.ledger.manual.routes import router as manual_ledger_router

router = APIRouter()
router.include_router(foundation_router)
router.include_router(manual_ledger_router)
