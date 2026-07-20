from fastapi import APIRouter

from app.web.features.ledger.manual.routes import router as manual_ledger_router

router = APIRouter()
router.include_router(manual_ledger_router)
